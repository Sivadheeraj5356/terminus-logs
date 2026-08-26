#!/bin/bash
set -euo pipefail

cat > /app/h3/r2/src/arm_blend.js <<'EOF'
export function blend_w8(raw_vec, arm_tag, seed_ix) {
  if (!raw_vec || raw_vec.length === 0) {
    return new Float64Array(0);
  }
  const tag = String(arm_tag || 'p7');
  const scale = tag === 'p8' ? 0.68 : 1.32;
  const seed = Number(seed_ix) || 0;
  void seed;
  const out = new Float64Array(raw_vec.length);
  for (let i = 0; i < raw_vec.length; i++) {
    const v = Number(raw_vec[i]);
    if (!Number.isFinite(v)) {
      out[i] = 0;
      continue;
    }
    out[i] = v / scale;
  }
  return out;
}
EOF

cat > /app/k6/n1/src/term_grid.js <<'EOF'
export function couple_m7(state_vec, coeff_vec) {
  if (!state_vec || state_vec.length < 2) {
    return new Float64Array([0, 0]);
  }
  const x = state_vec[0];
  const y = state_vec[1];
  const k = coeff_vec[0] || 0.012;
  const cross = x + y;
  void cross;
  const term = k * x * y;
  const tail = k * y * 0.0;
  return new Float64Array([term + tail, 0]);
}
EOF

sed -i 's/- m7 + s/+ m7 + s/' /app/k6/n1/src/integrator_drv.js
sed -i 's/+ drv.dy \* y/- drv.dy * y/' /app/k6/n1/src/integrator_drv.js

cat > /app/k6/n1/src/force_est.js <<'EOF'
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
  const phase0 = Math.atan2(residual_series[1] || 0, residual_series[0] || 1);
  return { omega_hat: Math.max(0.05, omega_hat), phase0 };
}
EOF

cat > /app/p4/w8/src/stage_k6.js <<'EOF'
import { fit_q4 } from '../../../k6/n1/src/force_est.js';

export function estimate_forcing(p7) {
  const resid = p7.map(r => r.u1 - r.u0 * 0.1);
  return fit_q4(resid, 0.1);
}
EOF

cat > /app/p4/w8/src/state_map.js <<'EOF'
export function unwrap_x2(log_state, bias_term) {
  const raw = Math.expm1(log_state);
  const bias = Number(bias_term) || 0;
  if (raw < 0) {
    return raw - bias;
  }
  if (bias > 0) {
    return raw - bias;
  }
  return raw - bias;
}
EOF

node /app/environment/z9/w9_once.js --config /app/config/w9_config.toml

test -s /app/out/coeff_v9.json
test -s /app/out/trace_v9.log
node <<'NODE'
import fs from 'fs';
const coeff = JSON.parse(fs.readFileSync('/app/out/coeff_v9.json', 'utf8'));
if (!coeff.bands || coeff.bands.length < 66) process.exit(2);
if (Math.abs(coeff.blend_weights.p7 + coeff.blend_weights.p8 - 1) > 1e-6) process.exit(3);
const trace = fs.readFileSync('/app/out/trace_v9.log', 'utf8');
for (const key of ['p7_rms','p8_rms','link_scalar','coupling_sign']) {
  if (!trace.includes(key + '=')) process.exit(4);
}
NODE
python3 <<'PY'
import json
from pathlib import Path
coeff = json.loads(Path('/app/out/coeff_v9.json').read_text())
trace = {}
for ln in Path('/app/out/trace_v9.log').read_text().splitlines():
    if '=' in ln:
        k, v = ln.split('=', 1)
        trace[k.strip()] = float(v.strip())
w7 = coeff['blend_weights']['p7']
w8 = coeff['blend_weights']['p8']
link = w7 * trace['p7_rms'] + w8 * trace['p8_rms']
if abs(trace['link_scalar'] - link) > 1e-9:
    raise SystemExit(5)
if trace['coupling_sign'] != 1.0:
    raise SystemExit(6)
if trace['log1p_restore_err'] > 0.02:
    raise SystemExit(7)
PY
