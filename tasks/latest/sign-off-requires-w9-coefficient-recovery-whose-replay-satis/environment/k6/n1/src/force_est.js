export function fit_q4(residual_series, dt_step) {
  let num = 0;
  let den = 0;
  for (let i = 2; i < residual_series.length; i++) {
    const a = residual_series[i] - residual_series[i - 1];
    const b = residual_series[i - 2];
    num += a * b;
    den += b * b + 1e-12;
  }
  const omega_hat = Math.abs(num / den) * (2 * Math.PI) / Math.max(dt_step, 1e-6);
  const phase0 = Math.atan2(residual_series[0] || 1, residual_series[1] || 0);
  return { omega_hat: Math.max(0.05, omega_hat), phase0 };
}
