import { fit_q4 } from '../../../k6/n1/src/force_est.js';

export function estimate_forcing(p7) {
  const resid = p7.map(r => r.u1 - r.u0 * 0.11);
  return fit_q4(resid, 0.1);
}
