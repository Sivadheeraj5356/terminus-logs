import { blend_w8 } from '../../../h3/r2/src/arm_blend.js';

export function preprocess_profiles(p7, p8) {
  const p7u0 = blend_w8(new Float64Array(p7.map(r => r.u0)), 'p7', 0);
  const p8u0 = blend_w8(new Float64Array(p8.map(r => r.u0)), 'p8', 1);
  const p7_ref = p7.map(r => r.u0 / 1.32);
  const p8_ref = p8.map(r => r.u0 / 0.68);
  const rms = (a, b) => {
    const n = Math.min(a.length, b.length);
    let s = 0;
    for (let i = 0; i < n; i++) s += (a[i] - b[i]) ** 2;
    return Math.sqrt(s / Math.max(n, 1));
  };
  return {
    p7_rms: rms(Array.from(p7u0), p7_ref),
    p8_rms: rms(Array.from(p8u0), p8_ref),
  };
}
