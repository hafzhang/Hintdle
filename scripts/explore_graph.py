"""探索性分析：不同词集下的图连通性，并用 TAXI->POOP 验证与竞品数据是否一致。"""
from pathlib import Path
from collections import deque, defaultdict

RAW = Path(r"d:\wangzhan\hintdle\data\raw")


def load(name):
    return {
        w.strip().lower()
        for w in (RAW / name).read_text().splitlines()
        if len(w.strip()) == 4 and w.strip().isalpha()
    }


def build_adj(words):
    """通配桶建邻接表：每个词的每个位置替换为 *，同桶词互为一步邻居。"""
    buckets = defaultdict(list)
    for w in words:
        for i in range(4):
            buckets[w[:i] + "*" + w[i + 1:]].append(w)
    adj = defaultdict(set)
    for bucket in buckets.values():
        for a in bucket:
            adj[a].update(b for b in bucket if b != a)
    return adj


def bfs(adj, root):
    dist = {root: 0}
    paths = {root: 1}
    q = deque([root])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                paths[v] = paths[u]
                q.append(v)
            elif dist[v] == dist[u] + 1:
                paths[v] += paths[u]
    return dist, paths


def report(name, words):
    adj = build_adj(words)
    dist, paths = bfs(adj, "poop")
    reachable = len(dist)
    print(f"== {name}: {len(words)} words, reachable from POOP={reachable} "
          f"({reachable/len(words)*100:.1f}%), unreachable={len(words)-reachable}")
    if "taxi" in dist:
        print(f"   TAXI: distance={dist['taxi']}, shortest_paths={paths['taxi']}, "
              f"neighbors_of_POOP={len(adj['poop'])}")
    else:
        print("   TAXI unreachable!")
    # 距离分布
    hist = defaultdict(int)
    for d in dist.values():
        hist[d] += 1
    print("   distance dist:", dict(sorted(hist.items())))


en = load("enable1.txt")
sow = load("sowpods.txt")
goog = load("google_10000_frequency.txt")
dwyl = load("words_alpha_dwyl.txt")

report("SOWPODS only", sow)
report("ENABLE only", en)
report("UNION en|sow|google", en | sow | goog)
# dwyl 里有但不在精选并集中的词（潜在补充池）
extra = dwyl - (en | sow | goog)
print(f"\ndwyl-only candidates (not in curated union): {len(extra)}")
