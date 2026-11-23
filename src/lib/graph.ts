// Build-time reader for the word-ladder graph produced by scripts/build_official_graph.py.
// Everything below is computed from data/processed/word_ladder_4letter.csv — no network, no backend.
import fs from 'node:fs';
import path from 'node:path';

export const TARGET = 'poop';
const DATA_DIR = path.resolve(process.cwd(), 'data', 'processed');

export type Difficulty = 'Easy' | 'Medium' | 'Hard';

export interface WordInfo {
  word: string;
  distance: number;
  predecessor: string | null;
  pathCount: number;
  freq: number | null;
}

interface Graph {
  words: Map<string, WordInfo>;
  adj: Map<string, string[]>;
  sortedWords: string[];
}

function readCsv(file: string): string[][] {
  const text = fs.readFileSync(file, 'utf-8').trim();
  return text.split(/\r?\n/).map((line) => line.split(','));
}

function toInt(v: string | undefined): number | null {
  if (v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

let cached: Graph | null = null;

/** Load (once per build) the official 2,398-word graph plus its adjacency lists. */
export function getGraph(): Graph {
  if (cached) return cached;

  const rows = readCsv(path.join(DATA_DIR, 'word_ladder_4letter.csv'));
  const header = rows[0];
  const iw = header.indexOf('word');
  const id = header.indexOf('distance_to_poop');
  const ip = header.indexOf('predecessor');
  const ic = header.indexOf('shortest_path_count');
  const ifq = header.indexOf('official_freq');

  const words = new Map<string, WordInfo>();
  for (const r of rows.slice(1)) {
    const w = r[iw];
    if (!w) continue;
    const d = toInt(r[id]);
    if (d === null) continue; // unreachable rows are not part of the playable graph
    words.set(w, {
      word: w,
      distance: d,
      predecessor: r[ip] || null,
      pathCount: toInt(r[ic]) ?? 0,
      freq: toInt(r[ifq]),
    });
  }

  // Wildcard-bucket adjacency: two words are neighbours when they differ in exactly one letter.
  const buckets = new Map<string, string[]>();
  for (const w of words.keys()) {
    for (let i = 0; i < 4; i++) {
      const key = w.slice(0, i) + '*' + w.slice(i + 1);
      const arr = buckets.get(key);
      if (arr) arr.push(w);
      else buckets.set(key, [w]);
    }
  }
  const adjSet = new Map<string, Set<string>>();
  for (const w of words.keys()) adjSet.set(w, new Set());
  for (const bucket of buckets.values()) {
    for (const a of bucket) {
      for (const b of bucket) {
        if (a !== b) adjSet.get(a)!.add(b);
      }
    }
  }
  const adj = new Map<string, string[]>();
  for (const [w, s] of adjSet) adj.set(w, [...s].sort());

  cached = { words, adj, sortedWords: [...words.keys()].sort() };
  return cached;
}

export function difficultyOf(distance: number): Difficulty {
  if (distance <= 3) return 'Easy';
  if (distance <= 5) return 'Medium';
  return 'Hard';
}

export interface Solution {
  word: string;
  found: boolean;
  error?: string;
  distance: number;
  pathCount: number;
  difficulty: Difficulty;
  /** The predecessor-chain path used as the canonical answer. */
  best: string[];
  /** Up to `limit` distinct shortest paths, the canonical one first. */
  paths: string[][];
}

/** Solve one word against the graph. Pure lookup + local traversal. */
export function solveWord(input: string, limit = 6): Solution {
  const word = input.trim().toLowerCase();
  const { words, adj } = getGraph();
  const info = words.get(word);

  if (!info) {
    return {
      word,
      found: false,
      error: `"${word.toUpperCase()}" is not one of the playable four-letter words in the official ladder graph.`,
      distance: -1,
      pathCount: 0,
      difficulty: 'Easy',
      best: [],
      paths: [],
    };
  }

  const best: string[] = [word];
  let cur = word;
  while (cur !== TARGET) {
    const p = words.get(cur)!.predecessor;
    if (!p) break;
    cur = p;
    best.push(cur);
  }

  const paths: string[][] = [best];
  const seen = new Set<string>([best.join(' ')]);
  const dfs = (node: string, chain: string[]) => {
    if (paths.length >= limit) return;
    if (node === TARGET) {
      const key = chain.join(' ');
      if (!seen.has(key)) {
        seen.add(key);
        paths.push(chain);
      }
      return;
    }
    const d = words.get(node)!.distance;
    for (const nxt of adj.get(node)!) {
      if (words.get(nxt)!.distance === d - 1) dfs(nxt, [...chain, nxt]);
    }
  };
  dfs(word, [word]);

  return {
    word,
    found: true,
    distance: info.distance,
    pathCount: info.pathCount,
    difficulty: difficultyOf(info.distance),
    best,
    paths,
  };
}

export interface StepOption {
  word: string;
  distance: number;
  advances: boolean;
}

export interface LadderStep {
  from: string;
  distance: number;
  /** Neighbours that shorten the ladder (distance = current - 1). */
  options: StepOption[];
  /** Neighbours at the same level or further away — valid words that do not shorten the ladder. */
  nonProgress: StepOption[];
}

/** Per-step breakdown: every legal next move, and why the others are not shorter. */
export function ladderSteps(word: string): LadderStep[] {
  const { words, adj } = getGraph();
  const sol = solveWord(word, 1);
  if (!sol.found) return [];

  const steps: LadderStep[] = [];
  for (let i = 0; i < sol.best.length - 1; i++) {
    const cur = sol.best[i];
    const d = words.get(cur)!.distance;
    const options: StepOption[] = [];
    const nonProgress: StepOption[] = [];
    for (const n of adj.get(cur)!) {
      const nd = words.get(n)!.distance;
      if (nd === d - 1) options.push({ word: n, distance: nd, advances: true });
      else if (nd >= d) nonProgress.push({ word: n, distance: nd, advances: false });
    }
    // Prefer the words that also appear on other shortest paths, then alphabetical.
    options.sort((a, b) => b.distance - a.distance || a.word.localeCompare(b.word));
    // Closest-to-goal first; these are the plausible-looking dead ends worth explaining.
    nonProgress.sort((a, b) => a.distance - b.distance || a.word.localeCompare(b.word));
    steps.push({ from: cur, distance: d, options, nonProgress: nonProgress.slice(0, 6) });
  }
  return steps;
}

/** Words one letter away from `word` — used for the internal link web. */
export function neighbours(word: string, limit = 8): string[] {
  const { adj } = getGraph();
  return (adj.get(word) ?? []).slice(0, limit);
}

/** Stable per-word hash — used to give each page a different slice of its band. */
function hashWord(w: string): number {
  let h = 0;
  for (let i = 0; i < w.length; i++) h = (h * 31 + w.charCodeAt(i)) >>> 0;
  return h;
}

/**
 * Words in the same difficulty band, rotated per word.
 *
 * Taking the first N of the band would hand every page the same six links (the band is iterated
 * in data order), which turns 2,400 pages into a near-duplicate link block. Rotating the start
 * position by a hash of the word keeps the block deterministic but different on every page.
 */
export function sameDistancePeers(word: string, limit = 6): string[] {
  const { words } = getGraph();
  const info = words.get(word);
  if (!info) return [];
  const pool = [...words.values()]
    .filter((w) => w.word !== word && w.distance === info.distance)
    .map((w) => w.word);
  if (pool.length <= limit) return pool;
  const start = hashWord(word) % pool.length;
  return Array.from({ length: limit }, (_, i) => pool[(start + i) % pool.length]);
}

export interface GraphStats {
  word_count: number;
  reachable_count: number;
  max_distance: number;
  distance_histogram: Record<string, number>;
  farthest_words: [string, number][];
  root_one_step_neighbor_count: number;
  sequence_length: number;
  sequence_covers_until_utc: string;
}

export function getStats(): GraphStats {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'graph_stats.json'), 'utf-8')) as GraphStats;
}

export function getPoopNeighbours(): string[] {
  const data = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'poop_neighbors.json'), 'utf-8')) as {
    one_step_neighbors: string[];
  };
  return data.one_step_neighbors;
}
