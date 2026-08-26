const fs = require('fs');
const path = require('path');
const { simulate } = require('./simulate');
const { sample_aquifer_params } = require('./sample_aquifer_params');

const here = __dirname;
const cfg = JSON.parse(fs.readFileSync(path.join(here, 'site_config.json'), 'utf8'));

const outDir = path.join(here, 'output');
fs.mkdirSync(outDir, { recursive: true });

const g = {
  nx: cfg.nx,
  ny: cfg.ny,
  dx: cfg.Lx / cfg.nx,
  dy: cfg.Ly / cfg.ny,
};

const base = {
  vx: cfg.vx_mean,
  vy: cfg.vy_mean,
  alphaL: cfg.alphaL_mean,
  alphaT: cfg.alphaT_mean,
  Dm: cfg.Dm,
  rho_b: cfg.rho_b,
  Kd: cfg.Kd,
  theta: cfg.theta,
  lambda: cfg.lambda_mean,
};
const [Cbase, baseWells] = simulate(base, g, cfg);
fs.writeFileSync(
  path.join(outDir, 'baseline_final.csv'),
  Cbase.map((row) => row.join(',')).join('\n') + '\n',
);

const nwells = cfg.wells.length;
const wellConc = [];
for (let k = 0; k < cfg.n_samples; k++) {
  const p = sample_aquifer_params(cfg, k);
  const [, wv] = simulate(p, g, cfg);
  wellConc.push(wv);
}

const valid = wellConc.filter((row) => row.every((v) => Number.isFinite(v)));

function percentile(sorted, q) {
  const pos = q * (sorted.length - 1);
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  const frac = pos - lo;
  return sorted[lo] + frac * (sorted[hi] - sorted[lo]);
}

const summary = {
  seed: cfg.seed,
  n_samples: cfg.n_samples,
  n_discarded: cfg.n_samples - valid.length,
  exceedance_threshold: cfg.exceedance_threshold,
  baseline_wells: cfg.wells.map((w, i) => ({ id: w.id, value: baseWells[i] })),
  wells: cfg.wells.map((w, i) => {
    const col = valid.map((row) => row[i]).sort((a, b) => a - b);
    return {
      id: w.id,
      p05: percentile(col, 0.05),
      p50: percentile(col, 0.5),
      p95: percentile(col, 0.95),
    };
  }),
};
fs.writeFileSync(path.join(outDir, 'risk_summary.json'), JSON.stringify(summary));

let csv = 'well_id,x,y,exceedance_probability\n';
cfg.wells.forEach((w, i) => {
  const col = valid.map((row) => row[i]);
  const prob = col.filter((v) => v > cfg.exceedance_threshold).length / col.length;
  csv += `${w.id},${w.x},${w.y},${prob}\n`;
});
fs.writeFileSync(path.join(outDir, 'well_exceedance_probabilities.csv'), csv);
