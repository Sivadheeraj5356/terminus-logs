import { couple_m7 } from './term_grid.js';

function f_rhs(st, t, drv, coeff) {
  const x = st[0];
  const y = st[1];
  const m7 = couple_m7(st, coeff)[0];
  const s = drv.amp * Math.sin(drv.omega * t + drv.phase0);
  const dx = drv.rx * x * (1 - x / drv.kcap) - drv.alpha * x * y - m7 + s;
  const dy = drv.alpha * x * y + drv.dy * y;
  return [dx, dy];
}

export function rk4_drv(st0, t0, dt, steps, drv, coeff) {
  let st = st0.slice();
  let t = t0;
  const out = [];
  for (let i = 0; i < steps; i++) {
    out.push([t, st[0], st[1]]);
    const k1 = f_rhs(st, t, drv, coeff);
    const s2 = [st[0] + 0.5 * dt * k1[0], st[1] + 0.5 * dt * k1[1]];
    const k2 = f_rhs(s2, t + 0.5 * dt, drv, coeff);
    const s3 = [st[0] + 0.5 * dt * k2[0], st[1] + 0.5 * dt * k2[1]];
    const k3 = f_rhs(s3, t + 0.5 * dt, drv, coeff);
    const s4 = [st[0] + dt * k3[0], st[1] + dt * k3[1]];
    const k4 = f_rhs(s4, t + dt, drv, coeff);
    st = [
      st[0] + (dt / 6) * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
      st[1] + (dt / 6) * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
    ];
    t += dt;
  }
  return out;
}
