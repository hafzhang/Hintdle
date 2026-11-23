// Shared settings for the archive pagination.
import { getSequence, todayPuzzle, type Puzzle } from './daily';

export const PER_PAGE = 60;

/**
 * Every puzzle that has actually gone live, oldest first.
 *
 * #0 is skipped: its UTC window is zero-length and identical to #1's (both open at the
 * anchor, 2025-08-15 08:00 UTC), so it was never playable — it is the placeholder slot
 * at index 0 of the embedded sequence. The archive therefore starts at puzzle #1.
 */
export function releasedPuzzles(): Puzzle[] {
  const today = todayPuzzle();
  if (!today) return [];
  return getSequence().filter((p) => p.n >= 1 && p.n <= today.n);
}


/** Compact pager model: [1, '…', 4, 5, 6, '…', 20]. */
export function pagerItems(current: number, total: number, span = 2): (number | '…')[] {
  const items: (number | '…')[] = [];
  const push = (v: number | '…') => {
    if (items[items.length - 1] !== v) items.push(v);
  };
  for (let i = 1; i <= total; i++) {
    if (i === 1 || i === total || Math.abs(i - current) <= span) push(i);
    else push('…');
  }
  return items;
}

export function pagePath(page: number): string {
  return page === 1 ? '/archive/' : `/archive/page/${page}/`;
}
