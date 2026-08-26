export function histPrint(view) {
  const buckets = new Map();
  for (let r = 0; r < view.dim; r++) {
    const w = view.rp[r + 1] - view.rp[r];
    buckets.set(w, (buckets.get(w) || 0) + 1);
  }
  const lines = [];
  for (const [w, c] of [...buckets.entries()].sort((a, b) => a[0] - b[0])) {
    lines.push(`w=${w} c=${c}`);
  }
  return lines.join("\n");
}
