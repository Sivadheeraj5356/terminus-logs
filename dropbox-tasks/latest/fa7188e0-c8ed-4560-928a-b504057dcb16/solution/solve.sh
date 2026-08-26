#!/bin/bash
set -euo pipefail

cd /app

cat > /app/step_transport.js <<'EOF'
function step_transport(C, p, g, dt) {
  const ny = g.ny;
  const nx = g.nx;
  const dx = g.dx;
  const dy = g.dy;
  const vmag = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
  const Dxx = p.alphaL * p.vx * p.vx / vmag + p.alphaT * p.vy * p.vy / vmag + p.Dm;
  const Dyy = p.alphaL * p.vy * p.vy / vmag + p.alphaT * p.vx * p.vx / vmag + p.Dm;
  const Dxy = (p.alphaL - p.alphaT) * p.vx * p.vy / vmag;
  const R = 1 + p.rho_b * p.Kd / p.theta;

  const Cn = Array.from({ length: ny }, () => new Array(nx).fill(0));
  for (let j = 0; j < ny; j++) {
    const jm = j > 0 ? j - 1 : 0;
    const jp = j < ny - 1 ? j + 1 : ny - 1;
    for (let i = 0; i < nx; i++) {
      const im = i > 0 ? i - 1 : 0;
      const ip = i < nx - 1 ? i + 1 : nx - 1;
      const c = C[j][i];
      const d2x = (C[j][ip] - 2 * c + C[j][im]) / (dx * dx);
      const d2y = (C[jp][i] - 2 * c + C[jm][i]) / (dy * dy);
      const d2xy = (C[jp][ip] - C[jm][ip] - C[jp][im] + C[jm][im]) / (4 * dx * dy);
      const dCx = p.vx >= 0 ? (c - C[j][im]) / dx : (C[j][ip] - c) / dx;
      const dCy = p.vy >= 0 ? (c - C[jm][i]) / dy : (C[jp][i] - c) / dy;
      Cn[j][i] = c + dt * (1 / R) *
        (-(p.vx * dCx + p.vy * dCy) + Dxx * d2x + Dyy * d2y + 2 * Dxy * d2xy - p.lambda * c);
    }
  }
  return Cn;
}

module.exports = { step_transport };
EOF

cat > /app/simulate.js <<'EOF'
const { step_transport } = require('./step_transport');

function clampIdx(v, n) {
  return Math.min(Math.max(v, 0), n - 1);
}

function bilinear(C, wx, wy, dx, dy) {
  const ny = C.length;
  const nx = C[0].length;
  const gx = wx / dx - 0.5;
  const gy = wy / dy - 0.5;
  let i0 = Math.floor(gx);
  let j0 = Math.floor(gy);
  let fx = gx - i0;
  let fy = gy - j0;
  if (i0 < 0) { i0 = 0; fx = 0; }
  if (i0 > nx - 2) { i0 = nx - 2; fx = 1; }
  if (j0 < 0) { j0 = 0; fy = 0; }
  if (j0 > ny - 2) { j0 = ny - 2; fy = 1; }
  return (1 - fx) * (1 - fy) * C[j0][i0] + fx * (1 - fy) * C[j0][i0 + 1] +
    (1 - fx) * fy * C[j0 + 1][i0] + fx * fy * C[j0 + 1][i0 + 1];
}

function simulate(p, g, cfg) {
  let C = Array.from({ length: g.ny }, () => new Array(g.nx).fill(0));
  const dt = cfg.end_time / cfg.nsteps;
  const si = clampIdx(Math.round(cfg.source_x / g.dx - 0.5), g.nx);
  const sj = clampIdx(Math.round(cfg.source_y / g.dy - 0.5), g.ny);
  for (let n = 0; n < cfg.nsteps; n++) {
    C = step_transport(C, p, g, dt);
    C[sj][si] = cfg.source_conc;
    for (let j = 0; j < g.ny; j++) {
      for (let i = 0; i < g.nx; i++) {
        if (C[j][i] < 0) C[j][i] = 0;
      }
    }
  }
  const wellVals = cfg.wells.map((w) => bilinear(C, w.x, w.y, g.dx, g.dy));
  return [C, wellVals];
}

module.exports = { simulate };
EOF

cat > /app/sample_aquifer_params.js <<'EOF'
let rng = null;
let spare = null;

function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function normal() {
  if (spare !== null) {
    const s = spare;
    spare = null;
    return s;
  }
  let u1 = rng();
  const u2 = rng();
  if (u1 < 1e-300) u1 = 1e-300;
  const r = Math.sqrt(-2 * Math.log(u1));
  spare = r * Math.cos(2 * Math.PI * u2);
  return r * Math.sin(2 * Math.PI * u2);
}

function sample_aquifer_params(cfg, k) {
  if (k === 0 || rng === null) {
    rng = mulberry32(cfg.seed >>> 0);
    spare = null;
  }
  const sigma = Math.sqrt(Math.log(1 + cfg.cov * cfg.cov));
  const draw = (m) => Math.exp(Math.log(m) - 0.5 * sigma * sigma + sigma * normal());
  return {
    vx: draw(cfg.vx_mean),
    vy: draw(cfg.vy_mean),
    alphaL: draw(cfg.alphaL_mean),
    alphaT: draw(cfg.alphaT_mean),
    lambda: draw(cfg.lambda_mean),
    Dm: cfg.Dm,
    rho_b: cfg.rho_b,
    Kd: cfg.Kd,
    theta: cfg.theta,
  };
}

module.exports = { sample_aquifer_params };
EOF

cd /app
node /app/run_risk_study.js
