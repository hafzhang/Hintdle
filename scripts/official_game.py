"""
hintdle 官方游戏数据模块
========================
逆向 poople.io 前端 bundle（2026-11-22 验证）得到的确定性事实:

  - 每天北京时间 16:00（08:00 UTC）换题，锚点 2025-08-15 08:00 UTC。
  - 题号 Zt() = 自锚点起经过的天数（当天 08:00 UTC 后 +1）。
  - 官方可玩词图 xE = 2,398 个四字母词（含到 POOP 的 BFS 距离 0..11），
    在该词集上 BFS 与 xE/FE 距离 100% 吻合（2398/2398、1137/1137）。
  - 每日题目序列 FE = 1,137 期（PICK #0 ... HAIL #1136，够用到 2028-09），
    当日起始词 = FE[Zt()]。
  - 全部数据随普通 HTTP 下载的 JS bundle 分发，无需执行 JS。

  #464 基准（2026-11-22，浏览器实测）: JUGS，距离 5。

用法（作为库）:
  from official_game import download_bundle, parse_bundle, puzzle_number, today_word
"""
from __future__ import annotations

import json
import re
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(r"d:\wangzhan\hintdle")
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
DAILY = ROOT / "data" / "daily"
ROOT_WORD = "poop"
SITE = "https://poople.io"
ANCHOR = datetime(2025, 8, 15, 8, 0, 0, tzinfo=timezone.utc)  # Zt(): setUTCFullYear(2025,7,15), pe=8


# ---------------------------------------------------------------- 下载

def download_bundle(cache: Path | None = None, refresh: bool = False) -> str:
    """下载首页 HTML，定位当前 bundle，返回其内容文本。失败抛异常。"""
    if cache and cache.exists() and not refresh:
        return cache.read_text(encoding="utf-8", errors="replace")
    html = _get(SITE)
    m = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
    if not m:
        raise RuntimeError("poople.io homepage: bundle path not found (layout change?)")
    text = _get(SITE + m.group(1))
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
    return text


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _get(url: str, timeout: int = 30, retries: int = 3) -> str:
    last: Exception | None = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"GET {url} failed after {retries} tries: {last}")


# ---------------------------------------------------------------- 解析

def _template(bundle: str, var: str) -> str:
    i = bundle.index(f"{var}=`") + len(f"{var}=`")
    return bundle[i:bundle.index("`", i)]


def _lines(raw: str) -> list[str]:
    return [l.strip() for l in raw.split("\n") if l.strip()]


def parse_bundle(bundle: str) -> dict:
    """返回 {words, distances, sequence, freq}。"""
    # xE: 词,距离（距离=到 POOP 的 BFS 步数）
    xE = _lines(_template(bundle, "xE"))
    words: list[str] = []
    distances: dict[str, int] = {}
    for line in xE:
        line = line.rstrip("\\r").strip()
        if not line:
            continue
        w, _, d = line.partition(",")
        words.append(w.lower())
        distances[w.lower()] = int(d)

    # FE: 每日题目序列 word,distance（第 n 行 = 题号 #n）
    fe = _lines(_template(bundle, "FE"))
    sequence: list[tuple[str, int]] = []
    for line in fe:
        line = line.rstrip("\\r").strip()
        if not line:
            continue
        w, _, d = line.partition(",")
        sequence.append((w.lower(), int(d)))

    # D0: 词,频率计数（可选，用于排序展示）
    freq: dict[str, int] = {}
    if "D0=`" in bundle:
        for line in _lines(_template(bundle, "D0")):
            line = line.rstrip("\\r").strip()
            if not line:
                continue
            w, _, c = line.partition(",")
            if c.strip().isdigit():
                freq[w.lower()] = int(c)

    return {"words": words, "distances": distances, "sequence": sequence, "freq": freq}


# ---------------------------------------------------------------- 题号

def puzzle_number(now: datetime | None = None) -> int:
    """复现前端 Zt(): 逐日回退到锚点为止的步数。"""
    now = now or datetime.now(timezone.utc)
    n, cur = 0, now
    while cur > ANCHOR:
        cur -= timedelta(days=1)
        n += 1
    return n


def puzzle_start_utc(n: int) -> datetime:
    """题号 #n 的生效起点。

    实测（浏览器 2026-11-22T05:04Z 显示 #464，08:00Z 换题为 #465）:
    #n 的窗口为 [ANCHOR+(n-1)天, ANCHOR+n 天)。
    """
    return ANCHOR + timedelta(days=max(0, n - 1))


def today_word(parsed: dict, now: datetime | None = None) -> tuple[int, str]:
    n = puzzle_number(now)
    seq = parsed["sequence"]
    if n >= len(seq):
        raise RuntimeError(f"puzzle #{n} beyond embedded sequence ({len(seq)} puzzles) — bundle update needed")
    return n, seq[n][0]


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
    result: list[list[str]] = []

    def dfs(node, chain):
        if len(result) >= limit:
            return
        if node == end:
            result.append(chain)
            return
        for nxt in adj[node]:
            if dist.get(nxt) == dist[node] - 1:
                dfs(nxt, chain + [nxt])

    dfs(start, [start])
    return result


def solve(parsed: dict, start: str) -> dict:
    """对任意起始词求解：距离、前驱回溯路径、全部最短路径。"""
    start = start.lower()
    words = set(parsed["words"])
    if start not in words:
        return {"error": f"'{start}' is not in the official 2,398-word graph"}
    adj = build_adj(words)
    dist, pred, paths = bfs(adj, ROOT_WORD)
    if start not in dist:
        return {"error": f"'{start}' cannot reach {ROOT_WORD.upper()}"}
    chain = [start]
    cur = start
    while cur != ROOT_WORD:
        cur = pred[cur]
        chain.append(cur)
    return {
        "word": start,
        "distance": dist[start],
        "path_count": paths[start],
        "path": chain,
        "all_paths": all_shortest_paths(adj, dist, start, ROOT_WORD),
    }
