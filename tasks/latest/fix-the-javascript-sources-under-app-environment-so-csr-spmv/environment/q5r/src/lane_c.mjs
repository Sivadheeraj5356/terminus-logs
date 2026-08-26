export function fn_q5(view, x, tiles) {
  const n = view.dim;
  const y = new Float64Array(n);
  const t = Math.max(1, tiles | 0);
  const end = Math.min(n, t);
  for (let r = 0; r < end; r++) {
    let s = 0;
    for (let p = view.rp[r]; p < view.rp[r + 1]; p++) {
      s += view.vals[p] * x[view.cols[p]];
    }
    y[r] = s;
  }
  return y;
}
