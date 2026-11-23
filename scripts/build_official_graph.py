"""
从 poople.io bundle 重建官方 2,398 词图数据
=============================================
输出 data/processed/:
  - word_ladder_4letter.csv     每词: 距离/前驱/最短路径数/可达/官方频次
  - poop_neighbors.json         一步到 POOP 的词
  - graph_stats.json            图统计 + #464 JUGS 基准验证
  - daily_sequence.csv          全部 1,137 期题目序列（题号,词,距离）

用法:
  python build_official_graph.py          # 用本地缓存 bundle
  python build_official_graph.py --refresh  # 重新下载 bundle
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from official_game import (  # noqa: E402
    DAILY, OUT, RAW, ROOT_WORD, bfs, build_adj, download_bundle, parse_bundle,
    puzzle_number, puzzle_start_utc, solve,
)

CACHE = RAW / "poople_bundle.js"
# 基准: 2026-11-22 浏览器实测 poople.io 头部 "#464: JUGS"，FE 距离 5
BENCHMARK = {"number": 464, "word": "jugs", "distance": 5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="重新下载 bundle")
    args = ap.parse_args()

    bundle = download_bundle(CACHE, refresh=args.refresh)
    parsed = parse_bundle(bundle)
    words = set(parsed["words"])
    distances = parsed["distances"]
    sequence = parsed["sequence"]
    freq = parsed["freq"]
    print(f"[graph] official words={len(words)}, sequence={len(sequence)} puzzles, freq entries={len(freq)}")

    adj = build_adj(words)
    dist, pred, paths = bfs(adj, ROOT_WORD)

    # 一致性验证: 我们的 BFS 与官方 xE 距离必须 100% 一致
    mismatch = [(w, d, dist.get(w)) for w, d in distances.items() if dist.get(w) != d]
    assert not mismatch, f"distance mismatch vs embedded xE: {mismatch[:10]}"
    seq_mismatch = [(w, d, dist.get(w)) for w, d in sequence if dist.get(w) != d]
    assert not seq_mismatch, f"distance mismatch vs embedded FE: {seq_mismatch[:10]}"
    print(f"[validate] BFS distances match embedded data: {len(distances)}/{len(distances)} words, "
          f"{len(sequence)}/{len(sequence)} puzzles")

    # 基准验证: #464 = JUGS, 距离 5
    n_now = puzzle_number()
    if n_now <= BENCHMARK["number"]:
        got = sequence[BENCHMARK["number"]]
        assert got[0] == BENCHMARK["word"] and got[1] == BENCHMARK["distance"], got
        print(f"[validate] benchmark #{BENCHMARK['number']} = {got[0]} (distance {got[1]}) OK")

    OUT.mkdir(parents=True, exist_ok=True)

    # 主 CSV
    with (OUT / "word_ladder_4letter.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["word", "distance_to_poop", "predecessor", "shortest_path_count",
                    "reachable", "official_freq"])
        for word in sorted(words):
            w.writerow([word, dist.get(word, ""), pred.get(word) or "",
                        paths.get(word, 0), int(word in dist), freq.get(word, "")])
    print(f"[done] word_ladder_4letter.csv ({len(words)} rows)")

    # POOP 一步邻居
    neighbors = sorted(adj[ROOT_WORD])
    (OUT / "poop_neighbors.json").write_text(json.dumps({
        "root": ROOT_WORD,
        "one_step_neighbors": neighbors,
        "count": len(neighbors),
    }, indent=2), encoding="utf-8")
    print(f"[done] poop_neighbors.json ({len(neighbors)} neighbors)")

    # 完整题目序列
    with (OUT / "daily_sequence.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["puzzle_number", "word", "distance", "start_utc"])
        for i, (word, d) in enumerate(sequence):
            w.writerow([i, word, d, puzzle_start_utc(i).isoformat()])
    print(f"[done] daily_sequence.csv ({len(sequence)} puzzles)")

    # 图统计
    hist: dict[int, int] = defaultdict(int)
    for d in dist.values():
        hist[d] += 1
    unreachable = sorted(words - set(dist))
    stats = {
        "word_count": len(words),
        "root_word": ROOT_WORD,
        "source": "poople.io JS bundle (xE), verified by own BFS",
        "reachable_count": len(dist),
        "unreachable_count": len(unreachable),
        "unreachable_words": unreachable,
        "distance_histogram": dict(sorted(hist.items())),
        "max_distance": max(hist),
        "farthest_words": sorted(((w, d) for w, d in dist.items() if d >= max(hist) - 1),
                                 key=lambda x: (-x[1], x[0]))[:10],
        "root_one_step_neighbor_count": len(neighbors),
        "sequence_length": len(sequence),
        "sequence_covers_until_utc": puzzle_start_utc(len(sequence) - 1).isoformat(),
        "benchmark": {
            "puzzle_number": BENCHMARK["number"],
            "word": BENCHMARK["word"],
            "distance": BENCHMARK["distance"],
            "verified": "browser 2026-11-22: header showed '#464: JUGS'",
        },
    }
    (OUT / "graph_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[done] graph_stats.json")

    # 顺带生成今日 daily JSON（若 fetch_today 未跑）
    DAILY.mkdir(parents=True, exist_ok=True)
    n, word = n_now, sequence[n_now][0]
    print(f"[today] puzzle #{n} = {word} (distance {dist[word]})")


if __name__ == "__main__":
    main()
