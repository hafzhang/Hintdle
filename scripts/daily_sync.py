"""
hintdle 每日同步（每天北京时间 16:10 = 08:00 UTC 换题后 10 分钟运行）
====================================================================
平时只做两件事: 校验官方数据有没有变、把静态站重新构建一遍。

  1. 刷新 poople.io bundle，与本机 data/processed 逐条比对
       一致     -> 只记日志（站点的题按日期算，不依赖联网）
       有差异   -> 调 build_official_graph.py 重建词图与题目序列
       下载失败 -> 写 alerts.log 并降级，保留旧数据（绝不写半新半旧的数据）
  2. （仅在第一步成功刷新时）生成当日存档 data/daily/YYYY-MM-DD.json
  3. 执行 astro build —— 静态站的「今天」按构建时刻计算,
     不重建的话 /、/answer-today/、/hints/、/yesterday/ 会一直停在昨天
  4. 只产出 dist/，不做任何部署

退出码: 0 = 站点构建成功（校验可能已降级）；1 = 构建失败。

用法:
  python daily_sync.py               # 每日正常运行（联网校验 + 构建）
  python daily_sync.py --skip-fetch  # 跳过联网校验，只重新构建站点
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from official_game import DAILY, OUT, RAW, download_bundle, parse_bundle  # noqa: E402

ROOT = OUT.parent.parent
CACHE = RAW / "poople_bundle.js"
ALERTS = DAILY / "alerts.log"
SEQ_CSV = OUT / "daily_sequence.csv"
WORD_CSV = OUT / "word_ladder_4letter.csv"
BUILD_GRAPH = HERE / "build_official_graph.py"
FETCH_TODAY = HERE / "fetch_today.py"


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}", flush=True)


def alert(msg: str) -> None:
    """降级记录: 出问题时写一行告警，但不改动任何已发布数据。"""
    DAILY.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ALERTS.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    log(f"[ALERT] {msg}")


def run(cmd: list[str]) -> int:
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT).returncode


def build_site() -> int:
    """astro build；失败时清掉 Astro/Vite 缓存重试一次。

    一次被中断的构建会留下过期的编译元数据，之后每次构建都会报
    "No cached compile metadata found"，只有清缓存才能恢复。
    """
    npm = shutil.which("npm") or "npm"
    code = run([npm, "run", "build"])
    if code != 0:
        log("[warn] build failed - clearing Astro/Vite caches and retrying once")
        for cache in (ROOT / "node_modules" / ".astro", ROOT / "node_modules" / ".vite"):
            shutil.rmtree(cache, ignore_errors=True)
        code = run([npm, "run", "build"])
    return code


# ---------------------------------------------------------------- 比对

def local_sequence() -> list[tuple[str, int]]:
    rows = list(csv.reader(SEQ_CSV.read_text(encoding="utf-8").splitlines()))[1:]
    return [(r[1], int(r[2])) for r in rows if r]


def local_words() -> dict[str, int]:
    rows = list(csv.reader(WORD_CSV.read_text(encoding="utf-8").splitlines()))[1:]
    return {r[0]: int(r[1]) for r in rows if r and r[1]}


def compare(parsed: dict) -> list[str]:
    """bundle 与本机 processed 数据的差异；空列表代表一致。"""
    drift: list[str] = []

    remote_seq = [(w, d) for w, d in parsed["sequence"]]
    mine_seq = local_sequence()
    if len(remote_seq) != len(mine_seq):
        drift.append(f"sequence length {len(mine_seq)} -> {len(remote_seq)}")
    for i, (mine, remote) in enumerate(zip(mine_seq, remote_seq)):
        if mine != remote:
            drift.append(f"puzzle #{i}: {mine[0]}/{mine[1]} -> {remote[0]}/{remote[1]}")
            if len(drift) >= 5:
                drift.append("...")
                break

    remote_words = parsed["distances"]
    mine_words = local_words()
    if set(remote_words) != set(mine_words):
        drift.append(f"word set changed: local={len(mine_words)} remote={len(remote_words)}")
    else:
        changed = [(w, mine_words[w], remote_words[w]) for w in mine_words
                   if mine_words[w] != remote_words[w]]
        if changed:
            drift.append(f"{len(changed)} word distances changed, e.g. {changed[:3]}")
    return drift


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true",
                    help="跳过 bundle 校验，只重新构建站点")
    args = ap.parse_args()

    refreshed = False
    if not args.skip_fetch:
        try:
            parsed = parse_bundle(download_bundle(CACHE, refresh=True))
            drift = compare(parsed)
            if drift:
                alert("poople.io bundle changed: " + "; ".join(drift))
                log("rebuilding graph data from the refreshed bundle")
                if run([sys.executable, str(BUILD_GRAPH)]) != 0:
                    alert("build_official_graph failed; previous processed data kept")
                else:
                    refreshed = True
            else:
                refreshed = True
                log(f"bundle in sync ({len(parsed['sequence'])} puzzles, "
                    f"{len(parsed['words'])} words)")
        except Exception as e:  # noqa: BLE001 —— 降级路径必须兜住一切异常
            alert(f"bundle fetch/check failed, previous data kept: {e}")

    # 只有当缓存确实刷新过，才敢生成当日存档（否则可能写出过期的起始词）。
    if refreshed:
        if run([sys.executable, str(FETCH_TODAY), "--offline"]) != 0:
            log("[warn] today's archive was not written (see alerts.log)")

    if build_site() != 0:
        alert("astro build failed")
        return 1

    log("done - dist/ rebuilt" + ("" if refreshed else " (bundle check DEGRADED)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
