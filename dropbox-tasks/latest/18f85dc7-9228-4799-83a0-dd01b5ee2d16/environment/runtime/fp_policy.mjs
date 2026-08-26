export function withinTolerance(observed, expected, spec) {
  const eps = spec?.tolerance?.epsilon ?? 1e-9;
  for (let i = 0; i < observed.length; i += 1) {
    const o = observed[i];
    const e = expected[i];
    const denom = Math.max(Math.abs(e), 1.0);
    if (Math.abs(o - e) / denom > eps) {
      return false;
    }
  }
  return true;
}
