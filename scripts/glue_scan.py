"""搬运信号（glue）扫描器：在已归集的 Reddit 原始数据/差评文本里捞出"系统间手工搬运"类 receipts。

用法：python scripts/glue_scan.py [--root reddit-data] [--out reddit-data/glue_scan_raw_DATE.md]
"""

import argparse
import datetime
import os
import re

BANDS = {
    "manual": re.compile(
        r"manually (enter|entering|entered|input|type|typing|typed|key|keys|keying|copy|copying|"
        r"add|adding|adds|fill|filling|log|logging|track|tracking|update|updating|create|creating)"
        r"|manual (entry|entries|data entry|data-entry|input|work)"
        r"|hand[- ]?(enter|entering|type|typing|key|keying|written)"
        r"|by hand|retype|re-type|retyped|reenter|re-enter|re-entering|rekey|re-key"
        r"|enter (it |them |everything |all of it )?(manually|by hand)"
        r"|(typing|entering|copying|pasting) (it |them )?(all )?(in|into)",
        re.I,
    ),
    "nosync": re.compile(
        r"(doesn'?t|does not|don'?t|do not|won'?t|will not|isn'?t|is not|not|can'?t|cannot|doesnt|dont|aren'?t)"
        r" (sync|syncs|syncing|integrate|integrates|integrating|talk(?:s|ed)?\b|connect|communicate)"
        r"|no integration|without integration|integrat\w* (is )?(broken|missing|limited|terrible|awful|none|non-?existent)"
        r"|disconnect(ed|ion)? (between|with)|there is a disconnect|broken integration|integration gap"
        r"|(two|2|different|multiple) (separate )?(systems|platforms|programs|software|tools).{0,40}"
        r"(don'?t|doesn'?t|not|no) (talk|sync|connect|integrat)",
        re.I,
    ),
    "move": re.compile(
        r"export (it |them |this |that |all )?(to |into )?(excel|csv|spreadsheet|a spreadsheet)"
        r"|copy[- ]?(and )?(paste|pasting)|copying .{0,30}(into|from|over to)"
        r"|download .{0,30}(csv|spreadsheet|statements|reports|data)"
        r"|paste (it |them )?(into|in) ",
        re.I,
    ),
    "reconcile": re.compile(
        r"reconcil\w*|double[- ]?(data[- ]?)?entry|duplicate (entry|entries|data)"
        r"|(enter|input|type) .{0,20}(twice|two (places|systems|different))"
        r"|(two|2|multiple) (separate )?(systems|platforms|places)",
        re.I,
    ),
    "freq": re.compile(
        r"daily|every day|each day|every single day|weekly|every week|each week"
        r"|monthly|every month|each month|once a month|per month|all day"
        r"|\d+\s*(hours?|hrs?)\s*(a|per|every)\s*(day|week|month)"
        r"|half (my|the) (day|week)|the whole (day|week)",
        re.I,
    ),
}

# reconcile 是双关词（"reconcile these principles" / "reconciling my diet"），
# 必须同窗口出现财务/系统名才算搬运信号，否则全是噪声。
REQUIRE = {
    "reconcile": re.compile(
        r"\b(bank|account|accounts|statement|ledger|invoice|payment|payments|deposit|deposits|escrow|"
        r"trust|month[- ]?end|balance sheet|commission|commissions|sales tax|cam|quickbooks|xero|wave|"
        r"jobber|appfolio|buildium|freshbooks|transaction|transactions|bookkeep\w*|payroll|checking|"
        r"manual|receipts|rent)\b",
        re.I,
    ),
}

SKIP_MARKERS = ("etsy", "_files", ".tmp", "node_modules", ".git", "__pycache__", "glue_scan")
SOURCE_EXT = (".json", ".txt", ".csv")
DERIVED_EXT = (".md",)
MAX_BYTES = 8 * 1024 * 1024
WINDOW = 150
PER_BAND_CAP = 40


def clean(s):
    s = s.replace("\\n", " ").replace('\\"', '"').replace("\\/", "/")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def scan_file(path, rel):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return []
    except OSError:
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return []

    out = []
    for band, rx in BANDS.items():
        if band == "freq":
            continue
        req = REQUIRE.get(band)
        hits = 0
        for m in rx.finditer(text):
            if hits >= PER_BAND_CAP:
                break
            lo = max(0, m.start() - WINDOW)
            hi = min(len(text), m.end() + WINDOW)
            window = clean(text[lo:hi])
            if req is not None and not req.search(window):
                continue
            hits += 1
            context = text[max(0, m.start() - 250): min(len(text), m.end() + 250)]
            freq = bool(BANDS["freq"].search(context))
            line = text.count("\n", 0, m.start()) + 1
            out.append(
                {
                    "file": rel,
                    "line": line,
                    "band": band,
                    "freq": freq,
                    "text": window,
                }
            )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="reddit-data")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    today = datetime.date.today().isoformat()
    out_path = args.out or os.path.join("reddit-data", f"glue_scan_raw_{today}.md")

    by_dir = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        top = "_root" if rel_dir == "." else rel_dir.split(os.sep)[0]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if any(m in rel.lower() for m in SKIP_MARKERS):
                continue
            if not name.lower().endswith(SOURCE_EXT + DERIVED_EXT):
                continue
            derived = name.lower().endswith(DERIVED_EXT)
            for rec in scan_file(full, rel):
                rec["derived"] = derived
                by_dir.setdefault(top, []).append(rec)

    lines = [f"# 搬运信号（glue）原始扫描 — {today}", ""]
    lines.append("口径：`manual`（手工录入/搬运）｜`nosync`（系统不通）｜`move`（导出/复制粘贴）｜`reconcile`（对账/重复录入）")
    lines.append("`[F]` = 同一上下文出现频率词（daily/weekly/monthly/hours per day）")
    lines.append("")

    summary = []
    for top in sorted(by_dir):
        recs = by_dir[top]
        src = [r for r in recs if not r["derived"]]
        counts = {}
        for r in src:
            counts[r["band"]] = counts.get(r["band"], 0) + 1
        summary.append((top, len(src), len(recs) - len(src), counts))

    lines.append("## 汇总（source=原始数据命中 / derived=报告类命中）")
    lines.append("")
    lines.append("| 方向 | source | derived | manual | nosync | move | reconcile |")
    lines.append("|---|---|---|---|---|---|---|")
    for top, nsrc, nder, counts in summary:
        lines.append(
            f"| {top} | {nsrc} | {nder} | {counts.get('manual',0)} | {counts.get('nosync',0)} "
            f"| {counts.get('move',0)} | {counts.get('reconcile',0)} |"
        )
    lines.append("")

    for top, nsrc, nder, counts in summary:
        lines.append(f"## {top}")
        lines.append("")
        for band in ("manual", "nosync", "move", "reconcile"):
            band_recs = [r for r in by_dir[top] if r["band"] == band and not r["derived"]]
            if not band_recs:
                continue
            lines.append(f"### {top} / {band}（{len(band_recs)}）")
            lines.append("")
            for r in band_recs:
                flag = "[F] " if r["freq"] else ""
                lines.append(f"- {flag}`{r['file']}:{r['line']}` {r['text']}")
            lines.append("")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"wrote {out_path}")
    for top, nsrc, nder, counts in summary:
        print(f"{top:12s} source={nsrc:<4d} derived={nder:<4d} {counts}")


if __name__ == "__main__":
    main()
