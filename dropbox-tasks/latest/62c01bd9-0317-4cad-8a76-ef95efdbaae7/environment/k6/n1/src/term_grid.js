export function couple_m7(state_vec, coeff_vec) {
  if (!state_vec || state_vec.length < 2) {
    return new Float64Array([0, 0]);
  }
  const x = state_vec[0];
  const y = state_vec[1];
  const k = coeff_vec[0] || 0.012;
  const cross = x + y;
  const quad = x * cross;
  const damp = Math.abs(y) > 1e-6 ? y / (Math.abs(y) + 1e-9) : 1.0;
  const term = k * quad * damp;
  const tail = k * y * 0.01;
  return new Float64Array([term + tail, 0]);
}
