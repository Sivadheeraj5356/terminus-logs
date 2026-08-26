// Dense Float64Array product helper. Accurate on small dims, but the filled
// n*n workspace cannot satisfy the published nz_cap for suite packs.
export function denseProduct(view, x) {
  const n = view.dim;
  const A = new Float64Array(n * n);
  for (let r = 0; r < n; r++) {
    for (let p = view.rp[r]; p < view.rp[r + 1]; p++) {
      const c = view.cols[p];
      A[r * n + c] = view.vals[p];
      if (view.half && r !== c) A[c * n + r] = view.vals[p];
    }
  }
  const y = new Float64Array(n);
  for (let r = 0; r < n; r++) {
    let s = 0;
    for (let c = 0; c < n; c++) s += A[r * n + c] * x[c];
    y[r] = s;
  }
  return { y, nz_workspace: n * n };
}
