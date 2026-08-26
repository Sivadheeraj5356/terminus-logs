#!/usr/bin/env node
import fs from 'fs';
import { runFit } from '../p4/w8/src/fit_runner.js';

function parseArgs() {
  const out = { config: '/app/config/w9_config.toml' };
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--config' && argv[i + 1]) out.config = argv[++i];
  }
  return out;
}

function loadTomlLite(p) {
  const txt = fs.readFileSync(p, 'utf8');
  const cfg = { blend: { p7: 0.58, p8: 0.42 }, dt: 0.1, bias_term: 0.48, m7: 0.012, regen: true, out_dir: '/app/out' };
  for (const ln of txt.split('\n')) {
    const m = ln.match(/^\s*(p7|p8)\s*=\s*([0-9.]+)/);
    if (m) cfg.blend[m[1]] = Number(m[2]);
    if (ln.includes('bias_term')) cfg.bias_term = Number(ln.split('=')[1]);
    if (ln.includes('m7_scale')) cfg.m7 = Number(ln.split('=')[1]);
  }
  return cfg;
}

const args = parseArgs();
const cfg = loadTomlLite(args.config);
runFit(cfg);
