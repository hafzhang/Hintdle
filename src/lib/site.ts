// Site-wide constants and URL helpers.
export const SITE = {
  url: 'https://hintdle.com',
  name: 'Hintdle',
  tagline: 'Every rung of the ladder, one screen away.',
  target: 'poop',
  /** How often the daily puzzle flips, in human terms. */
  flipHuman: '08:00 UTC (16:00 Beijing)',
  /** Social share card (1200×630). */
  ogImage: '/og-image.png',
  /** Square brand mark used by Organization structured data. */
  logo: '/logo.png',
} as const;

/** Absolute URL for a site-root-relative path. */
export function abs(pathname: string): string {
  return new URL(pathname, SITE.url).href;
}

/** Normalise an internal link so it always matches the trailing-slash canonical form. */
export function link(pathname: string): string {
  if (pathname === '/') return '/';
  return pathname.endsWith('/') ? pathname : `${pathname}/`;
}

/** Title-case a four-letter word for display (JUGS, not jugs). */
export function upper(word: string): string {
  return word.toUpperCase();
}

/** "1 step" / "5 steps" */
export function steps(n: number): string {
  return `${n} step${n === 1 ? '' : 's'}`;
}
