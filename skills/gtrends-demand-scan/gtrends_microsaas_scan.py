# -*- coding: utf-8 -*-
"""
Google Trends micro SaaS 需求扫描（本项目：D:\\Projects\\Reddit）

与 D:\\Projects\\trends-monitor 的区别：
- 那个项目监控「短期爆发新词」，词根是工具后缀（Generator/Calculator…），不动它；
- 本脚本面向「micro SaaS 商业需求」：
  种子词 = 人群 × 场景 × 商业意图（购买前语言 / 职业人群 / B2B 工作流 / 价格语言 / Reddit 信号反推）；
  候选词先过商业意图过滤器（不发请求），再拉 12 个月曲线判定：
    - breakout_new：近 21 天之前全年热度 ≤ 1（全新爆发）
    - steady_grower：有历史热度但近 12 周均值 > 前 12 周 × GROWTH_RATIO（稳步增长，micro SaaS 主猎场）

用法：
    python -X utf8 scripts/gtrends_microsaas_scan.py            # 全量种子
    python -X utf8 scripts/gtrends_microsaas_scan.py --limit 3  # 调试
"""

import argparse
import datetime as dt
import json
import re
import time
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq
from pytrends import exceptions as pytrends_exc

# ---------------- 配置 ----------------
BASELINE_TERM = "GPTs"
BASELINE_DAILY_SEARCHES = 5000   # 仅作相对体量标尺（全球口径，geo=US 下偏粗略）
MIN_EST_DAILY = 50               # 估算日搜索量下限
GEO = ""                         # 全球：英文种子词天然覆盖英语市场；且 GPTs 基准量是口径一致的全球估算
TIMEFRAME_RELATED = "today 3-m"  # 相关查询窗口（3 个月，比 7 天更能压住新闻尖峰）
TIMEFRAME_YEAR = "today 12-m"    # 趋势判定窗口
GROWTH_RATIO = 1.3               # steady_grower：近 12 周均值 >= 前 12 周 × 1.3
MAX_CAND_PER_SEED = 5            # 每个种子词进入 12 个月判定的候选上限（控请求数）
REQUEST_INTERVAL = 15            # 秒；trends-monitor 定时任务共用同一出口 IP，务必保守
RATE_LIMIT_WAIT = 60
MAX_RETRIES = 3
MAX_CONSEC_429 = 3               # 连续限流失败达到此次数则终止扫描，保留已采集数据

OUT_DIR = Path.cwd() / "trends-scan"  # 输出到当前工作目录；复制本脚本到你的项目后从项目根运行

# ---------------- 种子词：人群 × 场景 × 商业意图 ----------------
SEEDS = {
    # 注：chase invoice / best software for 在 2026-09-20 试跑中 related 返回 0，已移除
    "Reddit信号反推": ["late payment", "trade journal"],
    "购买前语言": ["alternative to", "spreadsheet for", "template for"],
    "职业人群": ["for landlords", "for contractors", "for therapists", "for realtors"],
    "B2B工作流": ["booking software", "invoice template"],
    "价格语言": ["fee calculator"],
}

# ---------------- 商业意图过滤器（不发请求） ----------------
PROFESSIONS = (
    "accountant", "landlord", "realtor", "real estate", "dentist", "therapist", "contractor",
    "freelance", "agency", "salon", "gym", "church", "restaurant", "ecommerce", "shopify",
    "etsy", "clinic", "law", "lawyer", "firm", "nonprofit", "hoa", "plumber", "electrician",
    "cleaning", "landscap", "photographer", "coach", "consultant", "small business", "smb",
    "saas", "startup", "creator", "airbnb", "property manager", "wedding", "veterinar",
    "chiropract", "physio", "dental", "medspa", "med spa", "trucking", "construction",
)
WORKFLOWS = (
    "invoice", "invoicing", "billing", "booking", "scheduling", "schedule", "payroll",
    "compliance", "audit", "onboarding", "quote", "estimate", "proposal", "contract",
    "crm", "inventory", "timesheet", "time tracking", "expense", "tax", "bookkeep",
    "appointment", "client portal", "intake", "form", "waiver", "checklist", "reporting",
    "dashboard", "subscription", "membership", "waitlist", "review", "testimonial",
    "churn", "retention", "lead", "follow up", "follow-up", "reminder", "receipt",
    "work order", "dispatch", "route", "menu", "rent", "lease", "journal", "log",
)
INTENT_WORDS = (
    "software", "app", "tool", "template", "spreadsheet", "calculator", "pricing", "cost",
    "alternative", " vs ", "best", " for ", "tracker", "manager", "generator", "planner",
    "free", "online", "automation", "automate",
)
NEGATIVE = (
    "news", "meaning", "lyrics", "song", "movie", "film", "cast", "season", "episode",
    "trailer", "game", "gameplay", "download", "apk", "mod", "who is", "net worth",
    "died", "dead", "wife", "husband", "girlfriend", "boyfriend", "leak", "reddit",
    "twitter", "tiktok", "instagram", "youtube", "vs real", "meme", "drama", "scandal",
    "bake", "recipe", "lettuce", "street", "celebrity", "actress", "actor", "nfl",
    "nba", "mlb", "ufc", "wwe", "casino", "bet", "lottery",
)


def commercial_score(query: str) -> int:
    q = f" {query.lower()} "
    score = 0
    if any(p in q for p in PROFESSIONS):
        score += 2
    if any(w in q for w in WORKFLOWS):
        score += 2
    if any(i in q for i in INTENT_WORDS):
        score += 1
    if any(n in q for n in NEGATIVE):
        score -= 3
    # 纯大写专有名（名人/品牌）降权：除首词外还有 2 个以上大写词
    caps = [w for w in re.findall(r"[A-Za-z']+", query) if w[:1].isupper()]
    if len(caps) >= 2:
        score -= 1
    return score


def log(msg: str):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def fresh_client() -> TrendReq:
    return TrendReq(hl="en-US", tz=360, timeout=(10, 25))


def call_with_retry(fn, desc: str):
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        client = fresh_client()
        try:
            time.sleep(REQUEST_INTERVAL)
            return fn(client)
        except pytrends_exc.TooManyRequestsError:
            wait = RATE_LIMIT_WAIT * attempt
            log(f"  触发限流(429)，等待 {wait}s ({attempt}/{MAX_RETRIES})：{desc}")
            time.sleep(wait)
            last_err = "429"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            log(f"  请求失败：{desc} -> {last_err}")
            break
    raise RuntimeError(f"{desc} 失败：{last_err}")


def get_related(seed: str) -> list:
    """返回 [{query, kind, rise_pct}]，kind = rising / top。"""
    def _q(client):
        client.build_payload([seed], timeframe=TIMEFRAME_RELATED, geo=GEO)
        return client.related_queries()

    data = call_with_retry(_q, f"种子[{seed}] related")
    rel = data.get(seed, {}) or {}
    out = []
    rising = rel.get("rising")
    if rising is not None and not rising.empty:
        for _, row in rising.iterrows():
            v = row["value"]
            v = 5000 if str(v).lower() == "breakout" else float(v)
            if v >= 200:  # 商业线放低 rising 门槛：稳步增长词比 breakout 更值钱
                out.append({"query": row["query"], "kind": "rising", "rise_pct": v})
    top = rel.get("top")
    if top is not None and not top.empty:
        for _, row in top.head(10).iterrows():
            out.append({"query": row["query"], "kind": "top", "rise_pct": None})
    return out


def get_interest(kw_list, timeframe: str) -> pd.DataFrame:
    def _q(client):
        client.build_payload(kw_list, timeframe=timeframe, geo=GEO)
        df = client.interest_over_time()
        if df is None or df.empty:
            raise RuntimeError("interest_over_time 空数据")
        return df

    return call_with_retry(_q, f"热度 {kw_list}")


def analyze_year(cand: str, df: pd.DataFrame) -> dict:
    res = {"est_daily": None, "is_new": False, "year_max_before": None,
           "last12w_vs_first12w": None, "last3w_vs_prev3w": None,
           "lane": None}
    if df is None or cand not in df.columns or BASELINE_TERM not in df.columns:
        return res
    c = df[cand].astype(float)
    b = df[BASELINE_TERM].astype(float)
    if b.mean() > 0:
        res["est_daily"] = round(c.mean() / b.mean() * BASELINE_DAILY_SEARCHES)

    weekly = c.resample("W").mean() if hasattr(c, "resample") else c
    n = len(weekly)
    if n >= 24:
        first12, last12 = weekly.iloc[:12].mean(), weekly.iloc[-12:].mean()
        if first12 > 0:
            res["last12w_vs_first12w"] = round(last12 / first12, 2)
    if n >= 6:
        prev3, last3 = weekly.iloc[-6:-3].mean(), weekly.iloc[-3:].mean()
        if prev3 > 0:
            res["last3w_vs_prev3w"] = round(last3 / prev3, 2)

    # is_new：近 21 天之前全年最大热度 <= 1
    s = c.iloc[:-21] if len(c) > 21 else c.iloc[:0]
    if len(s):
        res["year_max_before"] = float(s.max())
        res["is_new"] = bool(s.max() <= 1)

    est = res["est_daily"]
    if est is None or est < MIN_EST_DAILY:
        return res
    rising_now = (res["last3w_vs_prev3w"] or 0) >= 1.1
    if res["is_new"] and rising_now:
        res["lane"] = "breakout_new"
    elif (not res["is_new"]) and (res["last12w_vs_first12w"] or 0) >= GROWTH_RATIO:
        res["lane"] = "steady_grower"
    return res


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    seeds = [(cat, s) for cat, lst in SEEDS.items() for s in lst]
    if args.limit:
        seeds = seeds[: args.limit]
    scan_date = dt.date.today().isoformat()
    OUT_DIR.mkdir(exist_ok=True)
    log(f"micro SaaS 需求扫描：{len(seeds)} 个种子词，geo={GEO}")

    all_candidates, qualified, errors = [], [], []
    partial_file = OUT_DIR / f"partial_microsaas_scan_{scan_date}.json"

    def dump_partial():
        partial_file.write_text(json.dumps(
            {"candidates": all_candidates, "qualified": qualified, "errors": errors},
            ensure_ascii=False, default=str), encoding="utf-8")

    consec_429 = 0

    def is_429(err: RuntimeError) -> bool:
        return "429" in str(err)

    aborted = False
    for idx, (cat, seed) in enumerate(seeds, 1):
        if aborted:
            break
        log(f"({idx}/{len(seeds)}) [{cat}] {seed}")
        try:
            related = get_related(seed)
            consec_429 = 0
        except RuntimeError as e:
            errors.append({"seed": seed, "error": str(e)})
            if is_429(e):
                consec_429 += 1
                if consec_429 >= MAX_CONSEC_429:
                    log(f"  连续 {consec_429} 次限流，终止扫描，保留已采集数据")
                    aborted = True
            dump_partial()
            continue

        scored = []
        for r in related:
            sc = commercial_score(r["query"])
            r.update({"seed": seed, "category": cat, "commercial_score": sc})
            all_candidates.append(dict(r))
            if sc >= 2:
                scored.append(r)
        # 优先 rising（按涨幅排序），再 top；每种子上限 MAX_CAND_PER_SEED
        scored.sort(key=lambda r: (r["kind"] != "rising", -(r["rise_pct"] or 0)))
        picked = scored[:MAX_CAND_PER_SEED]
        log(f"  related {len(related)} 条，商业过滤后 {len(scored)} 条，取 {len(picked)} 条判定")
        for r in picked:
            log(f"    → {r['query']} (score={r['commercial_score']}, {r['kind']})")

        for batch in chunks([r["query"] for r in picked], 4):
            try:
                df = get_interest(batch + [BASELINE_TERM], TIMEFRAME_YEAR)
                consec_429 = 0
            except RuntimeError as e:
                errors.append({"seed": seed, "error": str(e)})
                if is_429(e):
                    consec_429 += 1
                    if consec_429 >= MAX_CONSEC_429:
                        log(f"  连续 {consec_429} 次限流，终止扫描，保留已采集数据")
                        aborted = True
                        break
                continue
            for cand in batch:
                stats = analyze_year(cand, df)
                for r in all_candidates:
                    if r["seed"] == seed and r["query"] == cand:
                        r.update(stats)
                        if r.get("lane"):
                            qualified.append(dict(r))
                        break
        dump_partial()

    log(f"扫描完成：候选 {len(all_candidates)} 条，入库 {len(qualified)} 条")

    df_all = pd.DataFrame(all_candidates)
    df_q = pd.DataFrame(qualified)
    df_e = pd.DataFrame(errors)
    out_file = OUT_DIR / f"microsaas_scan_{scan_date}.xlsx"
    with pd.ExcelWriter(out_file, engine="openpyxl") as w:
        (df_q if not df_q.empty else pd.DataFrame([{"提示": "本次无入库词"}])).to_excel(w, sheet_name="qualified", index=False)
        (df_all if not df_all.empty else pd.DataFrame([{"提示": "无候选"}])).to_excel(w, sheet_name="all_candidates", index=False)
        (df_e if not df_e.empty else pd.DataFrame([{"提示": "无错误"}])).to_excel(w, sheet_name="errors", index=False)
    log(f"结果写入：{out_file}")

    print("\n===== 入库词 =====")
    for r in sorted(qualified, key=lambda x: -(x.get("est_daily") or 0)):
        print(f"  [{r['lane']}] {r['query']}  |  种子:{r['seed']}  est_daily:{r.get('est_daily')}  "
              f"12周增长:{r.get('last12w_vs_first12w')}  is_new:{r.get('is_new')}")


if __name__ == "__main__":
    main()
