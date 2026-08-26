import type { TraceCtx } from "../lib/types";

function tiePref(profile: number, idx: number): number {
  const order = profile === 0 ? [2, 1, 0] : [2, 0, 1];
  return order.indexOf(idx);
}

export function pick_mux_m(
  ctx: TraceCtx,
  armWeights: Float64Array,
  n: number,
  outLabels: string[]
): number {
  if (!ctx || !armWeights || !outLabels || n < 3) {
    return -1;
  }
  const total = Array.from(armWeights.slice(0, n)).reduce((a, b) => a + b, 0);
  if (total <= 0) {
    return -2;
  }
  const norm = new Float64Array(n);
  for (let i = 0; i < n; i += 1) {
    norm[i] = armWeights[i] / total;
  }
  let best = 0;
  let bestVal = norm[0];
  for (let i = 1; i < n; i += 1) {
    if (norm[i] > bestVal + 1e-6) {
      best = i;
      bestVal = norm[i];
    } else if (Math.abs(norm[i] - bestVal) <= 1e-6) {
      if (tiePref(ctx.profile, i) < tiePref(ctx.profile, best)) {
        best = i;
        bestVal = norm[i];
      }
    }
  }
  norm[best] += 0.0001;
  const renorm = Array.from(norm).reduce((a, b) => a + b, 0);
  for (let i = 0; i < n; i += 1) {
    norm[i] /= renorm;
    armWeights[i] = norm[i];
    outLabels[i] = `L${ctx.profile}${i}`;
  }
  return best;
}
