"""
hintdle 分级提示引擎
====================
基于 build_word_graph.py 产出的 CSV，实现竞品验证过的四层 spoiler-safe 提示:
  Hint 1: 最优路径共几步（最弱）
  Hint 2: 第一步改动的是第几个字母位
  Hint 3: 该位置从什么字母变成什么字母
  Hint 4: 第一步的完整单词（最强，接近剧透）

用法:
  python hint_engine.py taxi
  python hint_engine.py taxi --json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

OUT = Path(r"d:\wangzhan\hintdle\data\processed")
ROOT_WORD = "poop"


def load_graph() -> dict[str, dict]:
    graph: dict[str, dict] = {}
    with (OUT / "word_ladder_4letter.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            graph[row["word"]] = {
                "distance": int(row["distance_to_poop"]) if row["distance_to_poop"] != "" else None,
                "predecessor": row["predecessor"] or None,
                "path_count": int(row["shortest_path_count"]),
                "reachable": row["reachable"] == "1",
            }
    return graph


def solve(graph: dict[str, dict], start: str) -> list[str]:
    """沿前驱链回溯 start -> POOP 的一条已验证最短路径。"""
    start = start.lower()
    if start not in graph or not graph[start]["reachable"]:
        return []
    chain = [start]
    cur = start
    while cur != ROOT_WORD:
        cur = graph[cur]["predecessor"]
        chain.append(cur)
    return chain


def build_hints(graph: dict[str, dict], start: str) -> dict:
    start = start.lower()
    if start not in graph:
        return {"error": f"'{start}' is not in the 4-letter word graph", "word": start}
    if not graph[start]["reachable"]:
        return {"error": f"'{start}' cannot reach {ROOT_WORD.upper()} in the current graph", "word": start}

    chain = solve(graph, start)
    first_from, first_to = chain[0], chain[1]
    changed_pos = next(i for i in range(4) if first_from[i] != first_to[i])

    return {
        "word": start,
        "target": ROOT_WORD,
        "optimal_steps": graph[start]["distance"],
        "shortest_path_count": graph[start]["path_count"],
        "hints": {
            "1_steps": f"The shortest ladder takes {graph[start]['distance']} step(s).",
            "2_position": f"Your first move changes letter #{changed_pos + 1} "
                          f"({first_from[changed_pos].upper()}).",
            "3_letter_change": f"Position {changed_pos + 1}: "
                               f"{first_from[changed_pos].upper()} -> {first_to[changed_pos].upper()}.",
            "4_first_word": f"The first word is {first_to.upper()} "
                            f"({first_from.upper()} -> {first_to.upper()}).",
        },
        "revealed_path": chain,
    }


def main():
    ap = argparse.ArgumentParser(description="hintdle 4-level spoiler-safe hint engine")
    ap.add_argument("word", help="starting 4-letter word, e.g. taxi")
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args()

    graph = load_graph()
    result = build_hints(graph, args.word)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if "error" in result:
        print(result["error"])
        return
    print(f"# {result['word'].upper()} -> {result['target'].upper()}")
    print(f"optimal steps : {result['optimal_steps']}")
    print(f"equal paths   : {result['shortest_path_count']}")
    for level, text in result["hints"].items():
        print(f"[{level}] {text}")
    print("full path     :", " -> ".join(w.upper() for w in result["revealed_path"]))


if __name__ == "__main__":
    main()
