// Daily puzzle timeline. Mirrors scripts/official_game.py exactly:
//   puzzle number Zt() counts days since the anchor 2025-08-15 08:00 UTC,
//   and puzzle #n is live from ANCHOR + (n-1) days for 24 hours.
import fs from 'node:fs';
import path from 'node:path';

const DATA_DIR = path.resolve(process.cwd(), 'data', 'processed');
const ANCHOR = Date.UTC(2025, 7, 15, 8, 0, 0); // 2025-08-15T08:00:00Z
const DAY = 86_400_000;

export interface Puzzle {
  n: number;
  word: string;
  distance: number;
  startUtc: Date;
  endUtc: Date;
}

let _seq: Puzzle[] | null = null;

export function getSequence(): Puzzle[] {
  if (_seq) return _seq;
  const text = fs.readFileSync(path.join(DATA_DIR, 'daily_sequence.csv'), 'utf-8').trim();
  _seq = text
    .split(/\r?\n/)
    .slice(1)
    .filter(Boolean)
    .map((row) => {
      const [n, word, distance, start] = row.split(',');
      const startUtc = new Date(start);
      return {
        n: Number(n),
        word,
        distance: Number(distance),
        startUtc,
        endUtc: new Date(startUtc.getTime() + DAY),
      };
    });
  return _seq;
}

/** Replicates the front-end Zt(): number of days elapsed since the anchor. */
export function puzzleNumber(now: Date = new Date()): number {
  let n = 0;
  let cur = now.getTime();
  while (cur > ANCHOR) {
    cur -= DAY;
    n += 1;
  }
  return n;
}

export function puzzleStart(n: number): Date {
  return new Date(ANCHOR + Math.max(0, n - 1) * DAY);
}

export function todayPuzzle(now: Date = new Date()): Puzzle | null {
  const seq = getSequence();
  return seq[puzzleNumber(now)] ?? null;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** e.g. "Nov 21, 2026" (UTC). */
export function fmtDate(d: Date): string {
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}

/** e.g. "2026-11-21". */
export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Stable machine-readable timestamp for structured data. */
export function isoStamp(d: Date): string {
  return d.toISOString();
}
