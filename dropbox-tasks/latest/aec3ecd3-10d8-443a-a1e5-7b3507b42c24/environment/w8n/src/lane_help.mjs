export function markCount(view) {
  let marks = 0;
  for (let r = 0; r < view.dim; r++) {
    for (let p = view.rp[r]; p < view.rp[r + 1]; p++) {
      if (view.cols[p] >= r) marks += 1;
    }
  }
  return marks;
}
