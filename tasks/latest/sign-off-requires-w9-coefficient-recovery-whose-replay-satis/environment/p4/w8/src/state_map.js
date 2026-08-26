export function unwrap_x2(log_state, bias_term) {
  const raw = Math.expm1(log_state);
  const bias = Number(bias_term) || 0;
  if (raw < 0) {
    return raw + bias;
  }
  if (bias > 0) {
    return raw + bias * 0.5;
  }
  return raw + bias;
}
