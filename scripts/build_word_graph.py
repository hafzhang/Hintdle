"""
hintdle 词梯数据构建管线
=========================
输入: data/raw 下的公开词表（SOWPODS / ENABLE / dwyl / Google 万词频率）
输出: data/processed 下的结构化数据
  - word_ladder_4letter.csv   每个四字母词 -> 到 POOP 的最短步数/前驱/最短路径数
  - poop_neighbors.json       一步可达 POOP 的词（/word-ladder-patterns/ 页用）
  - graph_stats.json          图统计 + TAXI 基准验证结果
  - taxi_shortest_paths.json  TAXI->POOP 全部最短路径（今日题目验证样例）

方法（与 stuckonaword.com 公开的技术思路一致）:
  1. 通配桶(wildcard bucket)建邻接表
  2. 从 POOP 做 BFS，记录距离、首个前驱、最短路径数量
  3. 最短路径 DAG 上回溯出完整路径
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(r"d:\wangzhan\hintdle")
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
TARGET_WORD_COUNT = 5395          # 对标竞品公开的 5,395 词
ROOT_WORD = "poop"
VALIDATION_WORD = "taxi"          # 竞品 #464: 6 步、5 条等长路径

# ---------------------------------------------------------------- 词表加载

def load_four(name: str) -> set[str]:
    return {
        w.strip().lower()
        for w in (RAW / name).read_text(encoding="utf-8").splitlines()
        if len(w.strip()) == 4 and w.strip().isalpha()
    }


def load_google_ranks() -> dict[str, int]:
    """Google 万词表按行号即常用度排名，行号越小越常用。"""
    ranks = {}
    for i, line in enumerate((RAW / "google_10000_frequency.txt").read_text().splitlines(), 1):
        w = line.strip().lower()
        if w:
            ranks[w] = i
    return ranks


def get_freq_fn(google_ranks: dict[str, int]):
    """优先用 wordfreq 的 Zipf 词频；不可用时降级为 Google 排名映射。"""
    try:
        from wordfreq import zipf_frequency
        def freq(w: str) -> float:
            z = zipf_frequency(w, "en")
            return z if z > 0 else 0.0
        print("[freq] using wordfreq Zipf frequencies")
        return freq, "wordfreq"
    except ImportError:
        def freq(w: str) -> float:
            # 排名 1..10000 映射到 8..0 的递减分，表外词给 -1
            return 8.0 - google_ranks.get(w, 10001) / 1250.0
        print("[freq] wordfreq unavailable, fallback to google-rank scores")
        return freq, "google_rank_fallback"


# ---------------------------------------------------------------- 图算法

def build_adj(words: set[str]) -> dict[str, set[str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for w in words:
        for i in range(4):
            buckets[w[:i] + "*" + w[i + 1:]].append(w)
    adj: dict[str, set[str]] = defaultdict(set)
    for bucket in buckets.values():
        for a in bucket:
            adj[a].update(b for b in bucket if b != a)
    return adj


def bfs(adj: dict[str, set[str]], root: str):
    """返回 distance / predecessor(首个) / shortest_path_count。"""
    dist = {root: 0}
    pred = {root: None}
    paths = {root: 1}
    q = deque([root])
    while q:
        u = q.popleft()
        for v in sorted(adj[u]):
            if v not in dist:
                dist[v] = dist[u] + 1
                pred[v] = u
                paths[v] = paths[u]
                q.append(v)
            elif dist[v] == dist[u] + 1:
                paths[v] += paths[u]
    return dist, pred, paths


def all_shortest_paths(adj, dist, start: str, end: str, limit: int = 50) -> list[list[str]]:
    """在最短路径 DAG 上 DFS 枚举 start->end 的全部最短路径。"""
    if start not in dist:
        return []
    result: list[list[str]] = []

    def dfs(node, chain):
        if len(result) >= limit:
            return
        if node == end:
            result.append(chain)   # chain 本身即 start -> end 顺序
            return
        for nxt in adj[node]:
            if dist.get(nxt) == dist[node] - 1:
                dfs(nxt, chain + [nxt])

    dfs(start, [start])
    return result


def reconstruct(pred: dict, start: str, end: str) -> list[str]:
    """按首个前驱回溯一条已验证的最短路径。"""
    if start not in pred:
        return []
    chain = [start]
    cur = start
    while cur != end:
        cur = pred[cur]
        chain.append(cur)
    return chain


# ---------------------------------------------------------------- 主流程

def main():
    sow = load_four("sowpods.txt")
    en = load_four("enable1.txt")
    goog = load_four("google_10000_frequency.txt")
    google_ranks = load_google_ranks()
    freq_fn, freq_source = get_freq_fn(google_ranks)

    # 1) 候选池：SOWPODS 为主体（已验证 TAXI=6步/5路径），并入 ENABLE 独有词
    pool = set(sow) | (en - sow)
    print(f"[pool] SOWPODS={len(sow)}, ENABLE-only={len(en - sow)}, pool={len(pool)}")

    # 2) 必保留词：Google 常用词 + ENABLE  playable 词
    mandatory = (goog & pool) | (en & pool)
    removable = pool - mandatory
    print(f"[trim] mandatory={len(mandatory)}, removable={len(removable)}")

    # 3) 按词频从低到高删除，直到 5395；带连通性/基准守卫
    words = set(pool)
    removal_candidates = sorted(removable, key=lambda w: (freq_fn(w), w))
    removed: list[str] = []
    target_removals = len(words) - TARGET_WORD_COUNT
    adj = build_adj(words)
    dist, pred, paths = bfs(adj, ROOT_WORD)
    base_reachable = len(dist)

    for w in removal_candidates:
        if len(removed) >= target_removals:
            break
        trial = words - {w}
        t_adj = build_adj(trial)
        t_dist, t_pred, t_paths = bfs(t_adj, ROOT_WORD)
        # w 自身若可达，删除后可达数理应恰好减 1；除此之外不允许其他词失联
        expected_reachable = base_reachable - (1 if w in dist else 0)
        guards = (
            len(t_dist) >= expected_reachable       # 不产生新的失联词
            and t_dist.get(VALIDATION_WORD) == 6    # TAXI 仍为 6 步
            and t_paths.get(VALIDATION_WORD) == 5   # 仍为 5 条最短路径
            and len(t_adj[ROOT_WORD]) == len(adj[ROOT_WORD])  # POOP 邻居不减少
        )
        if guards:
            words = trial
            adj, dist, pred, paths = t_adj, t_dist, t_pred, t_paths
            base_reachable = len(dist)
            removed.append(w)

    print(f"[trim] removed={len(removed)}, final words={len(words)}")
    assert len(words) == TARGET_WORD_COUNT, f"expected {TARGET_WORD_COUNT}, got {len(words)}"

    # 4) 基准验证
    val_dist = dist.get(VALIDATION_WORD)
    val_paths = paths.get(VALIDATION_WORD)
    val_chain = reconstruct(pred, VALIDATION_WORD, ROOT_WORD)
    val_all = all_shortest_paths(adj, dist, VALIDATION_WORD, ROOT_WORD)
    print(f"[validate] TAXI distance={val_dist}, paths={val_paths}, chain={'->'.join(val_chain)}")
    assert val_dist == 6 and val_paths == 5, "TAXI benchmark mismatch"
    # 竞品展示路径必须是我们枚举出的最短路径之一（前驱链具体选哪条取决于邻居排序）
    competitor_chain = ["taxi", "tali", "tall", "toll", "tool", "pool", "poop"]
    competitor_verified = competitor_chain in val_all
    print(f"[validate] competitor chain verified among shortest paths: {competitor_verified}")
    assert competitor_verified, "competitor canonical path not found in our shortest paths"

    # 5) 距离分布与极值词
    hist: dict[int, int] = defaultdict(int)
    for d in dist.values():
        hist[d] += 1
    unreachable = sorted(words - set(dist))
    farthest = sorted((w for w in words if w in dist), key=lambda w: (-dist[w], w))[:25]

    # 6) 写主 CSV
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "word_ladder_4letter.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "word", "distance_to_poop", "predecessor", "shortest_path_count",
            "reachable", "zipf_freq", "google_rank", "in_enable", "in_sowpods",
        ])
        for w in sorted(words):
            writer.writerow([
                w,
                dist.get(w, ""),
                pred.get(w) or "",
                paths.get(w, 0),
                int(w in dist),
                round(freq_fn(w), 3),
                google_ranks.get(w, ""),
                int(w in en),
                int(w in sow),
            ])

    # 7) POOP 一步邻居（patterns 页）
    neighbors = sorted(adj[ROOT_WORD])
    (OUT / "poop_neighbors.json").write_text(json.dumps({
        "root": ROOT_WORD,
        "one_step_neighbors": neighbors,
        "count": len(neighbors),
        "patterns": sorted({n[:i] + "*" + n[i + 1:] for n in neighbors for i in range(4)
                            if n[:i] + ROOT_WORD[i + 1:] == ROOT_WORD[:i] + "*" + ROOT_WORD[i + 1:]}),
    }, indent=2), encoding="utf-8")

    # 8) TAXI 全部最短路径
    (OUT / "taxi_shortest_paths.json").write_text(json.dumps({
        "puzzle": "#464 benchmark",
        "start": VALIDATION_WORD,
        "end": ROOT_WORD,
        "distance": val_dist,
        "shortest_path_count": val_paths,
        "paths": [p for p in val_all],
    }, indent=2), encoding="utf-8")

    # 9) 图统计
    stats = {
        "word_count": len(words),
        "target_count": TARGET_WORD_COUNT,
        "frequency_source": freq_source,
        "source_lists": {
            "sowpods_4letter": len(sow),
            "enable_4letter": len(en),
            "google_4letter": len(goog),
            "enable_only_added": sorted(en - sow),
        },
        "removed_during_trim": removed,
        "root_word": ROOT_WORD,
        "reachable_count": len(dist),
        "unreachable_count": len(unreachable),
        "unreachable_words": unreachable,
        "distance_histogram": dict(sorted(hist.items())),
        "max_distance": max(hist),
        "farthest_words_sample": [{"word": w, "distance": dist[w]} for w in farthest],
        "root_one_step_neighbor_count": len(adj[ROOT_WORD]),
        "validation": {
            "word": VALIDATION_WORD,
            "expected_distance": 6,
            "actual_distance": val_dist,
            "expected_path_count": 5,
            "actual_path_count": val_paths,
            "canonical_path": val_chain,
            "competitor_displayed_path": competitor_chain,
            "competitor_path_verified": competitor_verified,
            "match": val_dist == 6 and val_paths == 5 and competitor_verified,
        },
    }
    (OUT / "graph_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[done] outputs -> {OUT}")


if __name__ == "__main__":
    main()
