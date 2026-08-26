'use strict';

const { arc_m6 } = require('./ArcM6');
const { mix_z4 } = require('./MixZ4');

const B1 = 0.9;
const B2 = 0.999;
const EPS = 1e-8;

function echo_c(tbl) {
  if (!tbl || !tbl.lv) return [];
  return tbl.lv.map((v, i) => `${i}:${v}`);
}

function runTicks(frame, profile, idxFn, wallBase, viewA, viewB, from, to, partsSeed) {
  const parts = (partsSeed || []).slice();
  const curve = [];
  const tbl = { lv: profile.lv, stride: profile.stride, wall: wallBase };
  for (let t = from; t <= to; t++) {
    const wall = t - from + wallBase;
    const idx = idxFn(wall);
    const lr = arc_m6(idx, tbl);
    tbl.wall = wall;
    const x = Math.sin((frame.seed + t) * 0.17) * frame.gs;
    const grad = frame.a0.map((v, i) => x * (1 + 0.01 * i) + v * 0.001);
    const bc1 = 1 - Math.pow(B1, Math.max(idx, 1));
    const bc2 = 1 - Math.pow(B2, Math.max(idx, 1));
    let loss = 0;
    for (let i = 0; i < frame.dim; i++) {
      viewA[i] = B1 * viewA[i] + (1 - B1) * grad[i];
      viewB[i] = B2 * viewB[i] + (1 - B2) * grad[i] * grad[i];
      const mHat = viewA[i] / bc1;
      const vHat = viewB[i] / bc2;
      const upd = lr * mHat / (Math.sqrt(vHat) + EPS);
      loss += Math.abs(upd);
    }
    parts.push(loss);
    const tickStats = mix_z4(parts, parts.length);
    curve.push(tickStats.mean);
  }
  const stats = mix_z4(parts, parts.length);
  return { curve, stats, viewA, viewB, parts };
}

module.exports = { echo_c, runTicks };
