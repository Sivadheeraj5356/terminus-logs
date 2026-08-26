#!/bin/bash
set -euo pipefail

cp /app/h3/r2/src/arm_blend.js /app/h3/r2/src/arm_blend.save.js
cp /app/k6/n1/src/term_grid.js /app/k6/n1/src/term_grid.save.js
cp /app/k6/n1/src/force_est.js /app/k6/n1/src/force_est.save.js
cp /app/k6/n1/src/integrator_drv.js /app/k6/n1/src/integrator_drv.save.js
cp /app/p4/w8/src/state_map.js /app/p4/w8/src/state_map.save.js
cp /app/p4/w8/src/stage_k6.js /app/p4/w8/src/stage_k6.save.js

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

cat > /app/k6/n1/src/integrator_drv.js <<'EOF'
import { couple_m7 } from './term_grid.js';

function f_rhs(st, t, drv, coeff) {
  const x = st[0];
  const y = st[1];
  const m7 = couple_m7(st, coeff)[0];
  const s = drv.amp * Math.sin(drv.omega * t + drv.phase0);
  const dx = drv.rx * x * (1 - x / drv.kcap) - drv.alpha * x * y + m7 + s;
  const dy = drv.alpha * x * y - drv.dy * y;
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
EOF

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

node /app/z9/w9_once.js --config /app/config/w9_config.toml

python3 <<'PY'
import json
from pathlib import Path

coeff = json.loads(Path("/app/out/coeff_v9.json").read_text())
trace = {}
for ln in Path("/app/out/trace_v9.log").read_text().splitlines():
    if "=" in ln:
        k, v = ln.split("=", 1)
        trace[k.strip()] = float(v.strip())

if len(coeff.get("bands", [])) != 66:
    raise SystemExit("need 66 band rows from oracle replay")
if abs(coeff["blend_weights"]["p7"] + coeff["blend_weights"]["p8"] - 1.0) > 1e-6:
    raise SystemExit("blend weights must sum to one")
if trace.get("p7_rms", 999) > 0.08 or trace.get("p8_rms", 999) > 0.08:
    raise SystemExit("profile RMS out of class A bound during bake")

Path("/opt/w9_replay_snap.json").write_text(
    json.dumps({"trace": trace, "coeff": coeff}, indent=2) + "\n"
)
Path("/opt/w9_replay_snap.json").chmod(0o444)

ref_dir = Path("/app/ref")
ref_dir.mkdir(parents=True, exist_ok=True)
sidecar = ref_dir / "sidecar_table.csv"
lines = ["row_ix,slot_a,slot_b,slot_c,slot_d"]
for band in coeff["bands"]:
    lines.append(
        f"{band['row_ix']},{band['slot_a']},{band['slot_b']},{band['slot_c']},{band['slot_d']}"
    )
sidecar.write_text("\n".join(lines) + "\n")
sidecar.chmod(0o444)
PY

node --input-type=module <<'NODE'
import fs from 'fs';
import { rk4_drv } from '/app/k6/n1/src/integrator_drv.js';
import { unwrap_x2 } from '/app/p4/w8/src/state_map.js';
import { fit_q4 } from '/app/k6/n1/src/force_est.js';

function readCsv(p) {
  const txt = fs.readFileSync(p, 'utf8').trim().split('\n');
  const rows = [];
  for (let i = 1; i < txt.length; i++) {
    const [t, u0, u1] = txt[i].split(',').map(Number);
    rows.push({ t, u0, u1 });
  }
  return rows;
}

function segRms(traj, segRows, startIdx) {
  let sx = 0;
  let sy = 0;
  const n = segRows.length;
  for (let i = 0; i < n; i++) {
    const sample = traj[startIdx + i];
    sx += (sample[1] - segRows[i].u0) ** 2;
    sy += (sample[2] - segRows[i].u1) ** 2;
  }
  return {
    rms_x: Math.sqrt(sx / n),
    rms_y: Math.sqrt(sy / n),
  };
}

const bias = 0.48;
const p7 = readCsv('/app/data/q9/p7_traces.csv');
const resid = p7.map((r) => r.u1 - r.u0 * 0.1);
const { omega_hat, phase0 } = fit_q4(resid, 0.1);
const x0 = unwrap_x2(p7[0].u0, bias);
const drv = {
  rx: 0.75,
  kcap: 10,
  alpha: 0.018,
  dy: 0.28,
  amp: 0.22,
  omega: omega_hat,
  phase0,
};
const traj = rk4_drv([x0, p7[0].u1], 0, 0.1, 200, drv, [0.012]);
const segA = readCsv('/app/data/v9/segments/segment_a.csv');
const segB = readCsv('/app/data/v9/segments/segment_b.csv');
const snap = {
  segment_a: segRms(traj, segA, 40),
  segment_b: segRms(traj, segB, 120),
};
fs.writeFileSync('/opt/w9_segment_snap.json', JSON.stringify(snap, null, 2) + '\n');
fs.chmodSync('/opt/w9_segment_snap.json', 0o444);
NODE

mv /app/h3/r2/src/arm_blend.save.js /app/h3/r2/src/arm_blend.js
mv /app/k6/n1/src/term_grid.save.js /app/k6/n1/src/term_grid.js
mv /app/k6/n1/src/force_est.save.js /app/k6/n1/src/force_est.js
mv /app/k6/n1/src/integrator_drv.save.js /app/k6/n1/src/integrator_drv.js
mv /app/p4/w8/src/state_map.save.js /app/p4/w8/src/state_map.js
mv /app/p4/w8/src/stage_k6.save.js /app/p4/w8/src/stage_k6.js
rm -rf /app/out /app/tmp
