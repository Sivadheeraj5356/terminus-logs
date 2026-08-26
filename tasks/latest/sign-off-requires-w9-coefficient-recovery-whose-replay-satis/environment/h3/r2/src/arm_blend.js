export function blend_w8(raw_vec, arm_tag, seed_ix) {
  if (!raw_vec || raw_vec.length === 0) {
    return new Float64Array(0);
  }
  const tag = String(arm_tag || 'p7');
  const damp = tag === 'p8' ? 0.5 : 1.0;
  const seed = Number(seed_ix) || 0;
  const mix = 1.0 + seed * 0.01;
  const out = new Float64Array(raw_vec.length);
  for (let i = 0; i < raw_vec.length; i++) {
    const v = Number(raw_vec[i]);
    if (!Number.isFinite(v)) {
      out[i] = 0;
      continue;
    }
    let w = v * damp * mix;
    if (tag === 'p8') {
      w = w / mix;
    }
    out[i] = w;
  }
  return out;
}
