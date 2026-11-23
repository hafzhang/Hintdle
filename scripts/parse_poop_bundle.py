"""解析 poople.io 前端 bundle，提取内嵌题库与换题逻辑。

发现（2026-11-22）:
  - pe = 8               -> 每天 08:00 UTC 换题（与 poople.org 声明一致）
  - Zt()                 -> 题号 = 自 2025-08-15 08:00 UTC 起经过的天数
  - xE                   -> 内嵌 CSV "WORD,distance"，按 distance 升序
  - 无外部 API，fetch 调用仅为 React Router/Remix 框架内部
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(r"d:\wangzhan\hintdle")
BUNDLE = ROOT / "data" / "raw" / "poople_bundle.js"
ANCHOR = datetime(2025, 8, 15, 8, 0, 0, tzinfo=timezone.utc)  # Zt(): setUTCFullYear(2025,7,15), pe=8


def extract_csv(bundle_text: str) -> list[tuple[str, int]]:
    i = bundle_text.index("const xE=`") + len("const xE=`")
    j = bundle_text.index("`", i)
    raw = bundle_text[i:j]
    rows = []
    for line in re.split(r"(?:\\r|\\n|\r|\n)+", raw):
        line = line.strip()
        if not line:
            continue
        w, _, d = line.partition(",")
        rows.append((w.upper(), int(d)))
    return rows


def puzzle_number(now: datetime | None = None) -> int:
    """复现 Zt(): 从当前时刻往回退到锚点日期为止的天数。"""
    now = now or datetime.now(timezone.utc)
    n = 0
    cur = now
    while cur > ANCHOR:
        cur -= timedelta(days=1)
        n += 1
    return n


def main():
    text = BUNDLE.read_text(encoding="utf-8", errors="replace")
    rows = extract_csv(text)
    print(f"[bundle] embedded CSV rows: {len(rows)}")
    print(f"[bundle] first 5: {rows[:5]}")
    print(f"[bundle] last 5: {rows[-5:]}")

    # 距离分布
    hist: dict[int, int] = {}
    for _, d in rows:
        hist[d] = hist.get(d, 0) + 1
    print(f"[bundle] distance histogram: {dict(sorted(hist.items()))}")

    # 题号验证：今天(2026-11-22 08:00 UTC 后)应为 #464
    for probe in ["2026-11-22T09:00:00Z", "2026-11-22T07:00:00Z", "2026-11-21T17:00:00Z"]:
        n = puzzle_number(datetime.fromisoformat(probe.replace("Z", "+00:00")))
        print(f"[verify] {probe} -> puzzle #{n}")

    # 若题号直接索引 CSV（0 基），#464 应为 TAXI
    if len(rows) > 464:
        print(f"[verify] rows[464] = {rows[464]} (expect TAXI if index matches)")
        print(f"[verify] rows[463] = {rows[463]}, rows[465] = {rows[465]}")

    # 落盘：完整内嵌题库
    out = ROOT / "data" / "raw" / "poople_embedded_words.csv"
    out.write_text("\n".join(f"{w},{d}" for w, d in rows), encoding="utf-8")
    print(f"[done] saved -> {out}")

    # 与本地 5,395 词图对比
    local = {l.split(",")[0].strip().lower() for l in
             (ROOT / "data" / "processed" / "word_ladder_4letter.csv").read_text().splitlines()[1:]}
    embedded = {w.lower() for w, _ in rows}
    print(f"[compare] local={len(local)}, embedded={len(embedded)}, "
          f"only_in_embedded={sorted(embedded - local)[:20]}, only_in_local={len(local - embedded)}")


if __name__ == "__main__":
    main()
