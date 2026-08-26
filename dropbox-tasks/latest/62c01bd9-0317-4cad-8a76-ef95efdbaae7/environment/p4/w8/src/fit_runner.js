import fs from 'fs';
import path from 'path';
import { preprocess_profiles } from './stage_h3.js';
import { estimate_forcing } from './stage_k6.js';
import { unwrap_x2 } from './state_map.js';
import { rk4_drv } from '../../../k6/n1/src/integrator_drv.js';

function readCsv(p) {
  const txt = fs.readFileSync(p, 'utf8').trim().split('\n');
  const rows = [];
  for (let i = 1; i < txt.length; i++) {
    const [t, u0, u1] = txt[i].split(',').map(Number);
    rows.push({ t, u0, u1 });
  }
  return rows;
}

function rms(a, b) {
  const n = Math.min(a.length, b.length);
  let s = 0;
  for (let i = 0; i < n; i++) s += (a[i] - b[i]) ** 2;
  return Math.sqrt(s / Math.max(n, 1));
}

export function runFit(cfg) {
  const outDir = cfg.out_dir || '/app/out';
  const bias = cfg.bias_term ?? 0.48;
  if (cfg.regen && fs.existsSync(outDir)) {
    for (const f of fs.readdirSync(outDir)) fs.unlinkSync(path.join(outDir, f));
  }
  fs.mkdirSync(outDir, { recursive: true });
  fs.mkdirSync('/app/tmp', { recursive: true });

  const p7 = readCsv('/app/data/q9/p7_traces.csv');
  const p8 = readCsv('/app/data/q9/p8_traces.csv');
  const { p7_rms, p8_rms } = preprocess_profiles(p7, p8);
  const w7 = cfg.blend?.p7 ?? 0.58;
  const w8 = cfg.blend?.p8 ?? 0.42;
  const link_scalar = w7 * p7_rms + w8 * p8_rms;

  const { omega_hat, phase0 } = estimate_forcing(p7);

  const x0 = unwrap_x2(p7[0].u0, bias);
  const drv = { rx: 0.75, kcap: 10, alpha: 0.018, dy: 0.28, amp: 0.22, omega: omega_hat, phase0 };
  const coeff = [cfg.m7 ?? 0.012];
  const traj = rk4_drv([x0, p7[0].u1], 0, cfg.dt ?? 0.1, 200, drv, coeff);

  const segB = readCsv('/app/data/v9/segments/segment_b.csv');
  const trough = Math.min(...segB.map(r => r.u0));
  const peak = Math.max(...segB.map(r => r.u1));
  const log1p_restore_err = Math.abs(unwrap_x2(Math.log1p(trough + bias), bias) - trough);

  const bands = [];
  for (let ix = 0; ix < 66; ix++) {
    const off = ix * 2;
    const win = traj.slice(off, off + 20);
    const wx = win.map(r => r[1]);
    const wy = win.map(r => r[2]);
    const mx = wx.reduce((a, b) => a + b, 0) / wx.length;
    const my = wy.reduce((a, b) => a + b, 0) / wy.length;
    const sx = Math.sqrt(wx.reduce((a, v) => a + (v - mx) ** 2, 0) / wx.length);
    let num = 0;
    for (let j = 0; j < wx.length; j++) num += (wx[j] - mx) * (wy[j] - my);
    const sy = Math.sqrt(wy.reduce((a, v) => a + (v - my) ** 2, 0) / wy.length) + 1e-9;
    const corr = num / (wx.length * sx * sy + 1e-9);
    bands.push({ row_ix: ix + 1, slot_a: mx, slot_b: sx, slot_c: my, slot_d: corr });
  }

  const coeffDoc = {
    blend_weights: { p7: w7, p8: w8 },
    link_scalar,
    forcing: { omega_hat, phase0 },
    bands,
    profiles: { p7_rms, p8_rms },
  };
  fs.writeFileSync(path.join(outDir, 'coeff_v9.json'), JSON.stringify(coeffDoc, null, 2));

  const segA = readCsv('/app/data/v9/segments/segment_a.csv');
  const shift = Math.abs(segA[segA.length - 1].u0 - segB[0].u0);
  const skew = (Math.max(...segA.map(r => r.u0)) - Math.min(...segA.map(r => r.u0))) /
    (segA.reduce((a, r) => a + r.u0, 0) / segA.length + 1e-9);

  function segRms(trajRows, segRows, startIdx) {
    let sx = 0;
    let sy = 0;
    const n = segRows.length;
    for (let i = 0; i < n; i++) {
      const sample = trajRows[startIdx + i];
      sx += (sample[1] - segRows[i].u0) ** 2;
      sy += (sample[2] - segRows[i].u1) ** 2;
    }
    return { rms_x: Math.sqrt(sx / n), rms_y: Math.sqrt(sy / n) };
  }

  const segARms = segRms(traj, segA, 40);
  const segBRms = segRms(traj, segB, 120);

  const lines = [
    `p7_rms=${p7_rms}`,
    `p8_rms=${p8_rms}`,
    `link_scalar=${link_scalar}`,
    `phase_lag=${phase0}`,
    `seasonal_amp_p7=${drv.amp * 0.66}`,
    `seasonal_amp_p8=${drv.amp * 0.34}`,
    `trough_depth_b=${trough}`,
    `peak_height_b=${peak}`,
    `envelope_skew=${skew}`,
    `shift_metric=${shift}`,
    `log1p_restore_err=${log1p_restore_err}`,
    `coupling_sign=${coeff[0] >= 0 ? 1 : -1}`,
    `segment_a_rms_x=${segARms.rms_x}`,
    `segment_a_rms_y=${segARms.rms_y}`,
    `segment_b_rms_x=${segBRms.rms_x}`,
    `segment_b_rms_y=${segBRms.rms_y}`,
  ];
  for (const b of bands) {
    lines.push(`band_row_${b.row_ix}_slot_a=${b.slot_a}`);
    lines.push(`band_row_${b.row_ix}_slot_b=${b.slot_b}`);
    lines.push(`band_row_${b.row_ix}_slot_c=${b.slot_c}`);
    lines.push(`band_row_${b.row_ix}_slot_d=${b.slot_d}`);
  }
  fs.writeFileSync(path.join(outDir, 'trace_v9.log'), lines.join('\n') + '\n');
  fs.writeFileSync('/app/tmp/stage_p7.json', JSON.stringify({ p7_rms }));
  return coeffDoc;
}
