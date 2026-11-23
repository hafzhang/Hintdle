// Build-time generated lookup table for the client-side solver.
// Shape: { "<word>": { d, c, p, a } } where
//   d = shortest distance to POOP, c = number of shortest paths,
//   p = canonical shortest ladder (space-separated), a = up to 3 extra shortest ladders.
import type { APIRoute } from 'astro';
import { getGraph, solveWord } from '../lib/graph';

export const GET: APIRoute = () => {
  const { sortedWords } = getGraph();
  const out: Record<string, { d: number; c: number; p: string; a: string[] }> = {};

  for (const word of sortedWords) {
    const sol = solveWord(word, 4);
    if (!sol.found) continue;
    out[word] = {
      d: sol.distance,
      c: sol.pathCount,
      p: sol.best.join(' '),
      a: sol.paths
        .filter((p) => p.join(' ') !== sol.best.join(' '))
        .slice(0, 3)
        .map((p) => p.join(' ')),
    };
  }

  return new Response(JSON.stringify(out), {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
};
