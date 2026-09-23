# -*- coding: utf-8 -*-
"""
KD 批量查询（哥飞版关键词难度估算，seo.web.cafe/kd）

与 gtrends_microsaas_scan.py 互补：GTrends 出「量 + 趋势」，本脚本出「难度」。
项目方法论教训 12：预筛 KD 不能当结论，以哥飞版精评为准——本脚本即该精评的自动化入口。

额度纪律（三端共用：网页 / MCP / HTTP API）：
- 登录 100 次/天，VIP 500 次/天；每分钟 10 次保险丝 → 每词间隔 ≥6s
- 同词 7 天缓存命中仍计入额度 → 输入自动去重
- 429 quota（当日额度用完）立即终止，保留已采集

用法：
    python -X utf8 scripts/kd_scan.py "demand letter for unpaid rent" "eviction notice texas"
    python -X utf8 scripts/kd_scan.py --file words.txt            # 每行一个词
    python -X utf8 scripts/kd_scan.py --gl us --limit 5           # 限量防打爆日额度
    python -X utf8 scripts/kd_scan.py --md kd_summary.md          # 额外生成 Markdown 表格

令牌：环境变量 WC_KD_TOKEN 优先，其次 --token。不硬编码进脚本。
注意：keywordVolume 常为 null（API 体量口径不全），体量判断仍走 Google Ads 规划师。
"""

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import requests

API_URL = "https://seo.web.cafe/kd/api/v1/kd"
REQUEST_INTERVAL = 6.0   # 秒；配合每分钟 10 次保险丝
MAX_RETRIES = 3          # 429 rate 重试次数
RATE_LIMIT_WAIT = 30     # 429 rate 首退避秒数
OUT_DIR = Path(__file__).parent.parent / "reddit-data"


def log(msg: str):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_token(args) -> str:
    token = os.environ.get("WC_KD_TOKEN") or args.token
    if not token:
        sys.exit("缺少令牌：设置环境变量 WC_KD_TOKEN 或传 --token")
    return token


def fetch_kd(keyword: str, token: str, gl: str) -> dict:
    """查询单个词，返回原始响应 dict。quota 用尽抛 RuntimeError('quota')。"""
    headers = {"Authorization": f"Bearer {token}"}
    params = {"keyword": keyword, "gl": gl}
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(API_URL, params=params, headers=headers, timeout=30)
        except requests.RequestException as e:
            last_err = f"network: {e}"
            time.sleep(RATE_LIMIT_WAIT * attempt)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            body = r.text.lower()
            if "quota" in body or "额度" in body:
                raise RuntimeError("quota")
            log(f"  429 rate，退避 {RATE_LIMIT_WAIT * attempt}s（{attempt}/{MAX_RETRIES}）：{keyword}")
            time.sleep(RATE_LIMIT_WAIT * attempt)
            last_err = "429"
            continue
        last_err = f"HTTP {r.status_code}: {r.text[:200]}"
        break
    raise RuntimeError(f"{keyword} 查询失败：{last_err}")


def summarize(d: dict) -> dict:
    """压缩为汇总行。"""
    lb = d.get("linkBudget") or {}
    quality = lb.get("quality") or {}
    return {
        "keyword": d.get("keyword"),
        "score": d.get("score"),
        "level": d.get("level"),
        "keywordType": d.get("keywordType"),
        "volume": d.get("keywordVolume"),
        "volumeTrend": d.get("keywordTrend"),
        "linkBudget_mid": quality.get("mid"),
        "linkBudget_targetDr": lb.get("targetDr"),
        "cached": d.get("cached"),
        "computedAt": d.get("computedAt"),
        "reasons": d.get("reasons"),
        "details": d.get("details"),
    }


def print_table(rows: list):
    if not rows:
        return
    w = max(len(r["keyword"]) for r in rows)
    print(f"\n{'词'.ljust(w)} | {'KD':>5} | level | 链接预算(中值) | 体量 | 缓存")
    print("-" * (w + 56))
    for r in rows:
        vol = f"{r['volume']:,}" if isinstance(r["volume"], (int, float)) else "待核对"
        cached = "7d" if r["cached"] else "新算"
        lb = r["linkBudget_mid"] if r["linkBudget_mid"] is not None else "—"
        print(f"{r['keyword'].ljust(w)} | {r['score']:>5.1f} | {r['level']:<4} | {lb!s:>9} | {vol:<7} | {cached}")


def write_md(rows: list, path: Path):
    lines = [
        "# KD 精评结果（哥飞版接口自动查询）",
        f"\n> 查询时间：{dt.datetime.now():%Y-%m-%d %H:%M} ｜ 来源：https://seo.web.cafe/kd ｜ 体量待 Google Ads 核对\n",
        "| 词 | KD | level | 链接预算(中值) | 体量 | 缓存 |",
        "|---|---:|---|---|---:|---|",
    ]
    for r in rows:
        vol = f"{r['volume']:,}" if isinstance(r["volume"], (int, float)) else "待核对"
        cached = "7d 缓存" if r["cached"] else "新算"
        lb = r["linkBudget_mid"] if r["linkBudget_mid"] is not None else "—"
        lines.append(f"| {r['keyword']} | {r['score']} | {r['level']} | {lb} | {vol} | {cached} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Markdown 汇总：{path}")


def main():
    ap = argparse.ArgumentParser(description="哥飞版 KD 批量查询")
    ap.add_argument("keywords", nargs="*", help="关键词列表")
    ap.add_argument("--file", help="每行一个词的文件")
    ap.add_argument("--gl", default="us", help="Google 国家代码，默认 us")
    ap.add_argument("--token", help="API 令牌（优先用环境变量 WC_KD_TOKEN）")
    ap.add_argument("--limit", type=int, default=0, help="最多查 N 个词")
    ap.add_argument("--md", help="额外输出 Markdown 表格到该路径")
    args = ap.parse_args()

    token = load_token(args)
    words = list(args.keywords)
    if args.file:
        words += [ln.strip() for ln in Path(args.file).read_text(encoding="utf-8").splitlines() if ln.strip()]
    words = list(dict.fromkeys(words))  # 去重保序
    if args.limit:
        words = words[: args.limit]
    if not words:
        sys.exit("没有可查询的词：传关键词参数或 --file")

    OUT_DIR.mkdir(exist_ok=True)
    log(f"共 {len(words)} 个词（去重后），间隔 {REQUEST_INTERVAL}s")

    results, errors, abort = [], [], False
    for i, kw in enumerate(words, 1):
        log(f"({i}/{len(words)}) {kw}")
        try:
            d = fetch_kd(kw, token, args.gl)
            d["keyword"] = kw
            results.append(summarize(d))
            time.sleep(REQUEST_INTERVAL)
        except RuntimeError as e:
            if str(e) == "quota":
                log("今日额度用完（quota），终止，保留已采集")
                abort = True
                break
            errors.append({"keyword": kw, "error": str(e)})
        if abort:
            break

    ts = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    raw = {
        "queried_at": dt.datetime.now().isoformat(timespec="seconds"),
        "gl": args.gl,
        "summary": results,
        "errors": errors,
        "aborted_by_quota": abort,
    }
    out_file = OUT_DIR / f"kd_scan_{ts}.json"
    out_file.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"原始存档：{out_file}")

    print_table(results)
    if args.md:
        write_md(results, Path(args.md))
    if errors:
        print(f"\n⚠️ 失败 {len(errors)} 个：")
        for e in errors:
            print(f"  {e['keyword']}: {e['error']}")
    log(f"完成：成功 {len(results)} / 失败 {len(errors)}" + (" / 额度用尽中止" if abort else ""))


if __name__ == "__main__":
    main()
