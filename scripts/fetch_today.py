"""
hintdle 每日题目生成
====================
每天北京时间 16:10（08:00 UTC 换题后 10 分钟）运行:
  1. 重新下载 poople.io bundle（普通 HTTP，无需浏览器）
  2. 计算题号 Zt() 与当日起始词（bundle 内嵌序列，确定性）
  3. 本地 BFS 生成四层 spoiler-safe 提示 + 完整路径
  4. 落盘 data/daily/YYYY-MM-DD.json

降级铁律: 任一环节失败 -> 不写任何数据（错数据比不更新更伤），
          写告警日志 data/daily/alerts.log，昨日归档保持可访问。

用法:
  python fetch_today.py            # 正常每日运行（联网刷新 bundle）
  python fetch_today.py --offline # 用本地缓存 bundle 演练
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from official_game import (  # noqa: E402
    DAILY, RAW, ROOT_WORD, download_bundle, parse_bundle, puzzle_number,
    puzzle_start_utc, solve,
)

CACHE = RAW / "poople_bundle.js"
ALERTS = DAILY / "alerts.log"


def alert(msg: str) -> None:
    DAILY.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ALERTS.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[ALERT] {msg}")


def build_hint_payload(start: str, solution: dict) -> dict:
    """四层 spoiler-safe 提示（由弱到强），与竞品验证过的设计一致。"""
    first_from, first_to = start, solution["path"][1]
    changed_pos = next(i for i in range(4) if first_from[i] != first_to[i])
    return {
        "1_steps": f"The shortest ladder takes {solution['distance']} step(s).",
        "2_position": f"Your first move changes letter #{changed_pos + 1} ({first_from[changed_pos].upper()}).",
        "3_letter_change": (f"Position {changed_pos + 1}: "
                            f"{first_from[changed_pos].upper()} -> {first_to[changed_pos].upper()}."),
        "4_first_word": f"The first word is {first_to.upper()} ({first_from.upper()} -> {first_to.upper()}).",
    }


def run(offline: bool = False) -> Path | None:
    try:
        bundle = CACHE.read_text(encoding="utf-8", errors="replace") if offline else download_bundle(CACHE, refresh=True)
        parsed = parse_bundle(bundle)

        # bundle 更新导致序列变短/换序的防御: 起始词仍在图内、距离仍一致
        n = puzzle_number()
        if n >= len(parsed["sequence"]):
            raise RuntimeError(f"puzzle #{n} beyond embedded sequence; bundle not updated yet")
        word, seq_dist = parsed["sequence"][n]

        solution = solve(parsed, word)
        if "error" in solution:
            raise RuntimeError(f"solver error for #{n} {word}: {solution['error']}")
        if solution["distance"] != seq_dist:
            raise RuntimeError(
                f"distance mismatch: local BFS={solution['distance']}, bundle={seq_dist} for #{n} {word}")

        start_utc = puzzle_start_utc(n)
        payload = {
            "puzzle_number": n,
            "start_word": word,
            "target": ROOT_WORD,
            "date_utc": start_utc.date().isoformat(),
            "active_from_utc": start_utc.isoformat(),
            "active_until_utc": puzzle_start_utc(n + 1).isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "distance": solution["distance"],
            "shortest_path_count": solution["path_count"],
            "hints": build_hint_payload(word, solution),
            "revealed_path": solution["path"],
            "all_shortest_paths": solution["all_paths"],
        }

        DAILY.mkdir(parents=True, exist_ok=True)
        out = DAILY / f"{payload['date_utc']}.json"
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[done] #{n} {word} ({solution['distance']} steps, "
              f"{solution['path_count']} equal paths) -> {out}")
        return out
    except Exception as e:  # noqa: BLE001 —— 降级路径必须兜住一切异常
        alert(f"fetch_today failed, no data written: {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use cached bundle (dry run)")
    args = ap.parse_args()
    out = run(offline=args.offline)
    sys.exit(0 if out else 1)


if __name__ == "__main__":
    main()
