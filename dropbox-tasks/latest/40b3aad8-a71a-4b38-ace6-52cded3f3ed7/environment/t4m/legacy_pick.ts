import type { TraceCtx } from "../lib/types";

export function legacy_pick(_ctx: TraceCtx, weights: number[]): number {
  let best = 0;
  for (let i = 1; i < weights.length; i += 1) {
    if (weights[i] > weights[best]) {
      best = i;
    }
  }
  return best;
}
