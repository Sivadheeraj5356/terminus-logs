#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { readFrame, runUninterrupted, runResume, curveBytes, fnv1a32 } = require('../../n4/q7/src/LoopM3');
const { seal_k9 } = require('../../t2/y5/src/SealK9');

const ENV = process.env.APP_ROOT || '/app';
const BASE = path.join(ENV, 'environment');
const OUT = path.join(ENV, 'output');
const TRACE = path.join(OUT, 'traces');

function parseArgs(argv) {
  const out = { fullAudit: false, outPath: path.join(OUT, 'resume_witness.json') };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === '--full-audit') out.fullAudit = true;
    if (argv[i] === '--out' && argv[i + 1]) { out.outPath = argv[i + 1]; i++; }
  }
  return out;
}

function readTomlPairs(file) {
  const text = fs.readFileSync(file, 'utf8');
  const fixtures = [];
  const profiles = [];
  let section = null;
  let cur = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    if (line === '[[fixture]]') {
      if (cur && section === 'fixture') fixtures.push(cur);
      else if (cur && section === 'profile') profiles.push(cur);
      cur = {}; section = 'fixture'; continue;
    }
    if (line === '[[profile]]') {
      if (cur && section === 'fixture') fixtures.push(cur);
      else if (cur && section === 'profile') profiles.push(cur);
      cur = {}; section = 'profile'; continue;
    }
    const m = line.match(/^([a-z_]+)\s*=\s*(.+)$/);
    if (!m || !cur) continue;
    const key = m[1];
    let val = m[2].trim();
    if (val.startsWith('[')) {
      cur[key] = val.slice(1, -1).split(',').map((s) => {
        s = s.trim();
        if (s.startsWith('"')) return s.slice(1, -1);
        return Number(s);
      });
    } else {
      val = val.replace(/^"|"$/g, '');
      if (['ticks', 'pause', 'stride'].includes(key)) cur[key] = Number(val);
      else if (['band_max', 'band_tail'].includes(key)) cur[key] = Number(val);
      else cur[key] = val;
    }
  }
  if (cur) {
    if (section === 'fixture') fixtures.push(cur);
    if (section === 'profile') profiles.push(cur);
  }
  return { fixtures, profiles };
}

function loadHold() {
  const hold = [];
  let cur = null;
  for (const raw of fs.readFileSync(path.join(BASE, 'data/hold_q3.toml'), 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    if (line === '[[hold]]') { if (cur) hold.push(cur); cur = {}; continue; }
    const m = line.match(/^([a-z_]+)\s*=\s*(.+)$/);
    if (!m || !cur) continue;
    cur[m[1]] = m[2].trim().replace(/^"|"$/g, '');
  }
  if (cur) hold.push(cur);
  return hold;
}

function readJson(p, fb) {
  if (!fs.existsSync(p)) return fb;
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function writeJson(p, obj) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(obj, null, 2) + '\n');
}

function bandDrift(a, b) {
  const n = Math.min(a.length, b.length);
  let max = 0;
  let tail = 0;
  const tailStart = Math.floor(n * 0.7);
  for (let i = 0; i < n; i++) {
    const d = Math.abs(a[i] - b[i]);
    if (d > max) max = d;
    if (i >= tailStart) tail += d;
  }
  return { band_drift: max, band_tail: tail / Math.max(1, n - tailStart) };
}

function writeTrace(key, curve) {
  const body = curveBytes(curve);
  const trace = Buffer.concat([Buffer.from('K7TR'), body]);
  fs.mkdirSync(TRACE, { recursive: true });
  fs.writeFileSync(path.join(TRACE, `${key}.bin`), trace);
  return trace;
}

function rebuild() {
  const sh = path.join(BASE, 'scripts/build_all.sh');
  if (!fs.existsSync(sh)) return;
  try {
    execSync('bash ' + sh, { cwd: BASE, stdio: 'inherit' });
  } catch (_) {
    /* build helper optional when bash unavailable */
  }
}

function fullAudit(outPath) {
  rebuild();
  fs.mkdirSync(OUT, { recursive: true });
  fs.mkdirSync(TRACE, { recursive: true });
  const { fixtures, profiles } = readTomlPairs(path.join(BASE, 'data/lim_k7.toml'));
  const hold = loadHold();
  const ids = fs.readFileSync(path.join(BASE, 'guide/id_list.txt'), 'utf8')
    .split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  const dur = readJson(path.join(BASE, 'data/dur_k7.json'), { rows: {} });
  const snap = readJson(path.join(BASE, 'data/snap_k7.json'), { rows: {} });
  dur.snapRows = snap.rows || {};

  const rows = [];
  const pairs = [];
  for (const fx of fixtures) {
    if (!ids.includes(fx.id)) continue;
    for (const prof of profiles) {
      pairs.push({ fx, prof });
    }
  }
  for (const h of hold) {
    const fx = fixtures.find((f) => f.id === h.fixture);
    const prof = profiles.find((p) => p.name === h.profile);
    if (fx && prof) pairs.push({ fx, prof, hold: true });
  }

  for (const pair of pairs) {
    const raw = fs.readFileSync(path.join(BASE, 'fixtures/frames', pair.fx.frame));
    const frame = readFrame(raw);
    const kid = `${pair.fx.id}:${pair.prof.name}`;
    const cu = runUninterrupted(frame, pair.prof);
    const cr = runResume(frame, pair.prof);
    const digestU = fnv1a32(curveBytes(cu));
    const digestR = fnv1a32(curveBytes(cr));
    const bands = bandDrift(cu, cr);
    const tag = kid.replace(':', '_');
    const trace = writeTrace(tag, cu);
    seal_k9(dur, kid, trace);
    rows.push({
      fixture: pair.fx.id,
      profile: pair.prof.name,
      mode: 'uninterrupted',
      curve_digest: digestU,
      band_drift: bands.band_drift,
      band_tail: bands.band_tail,
    });
    rows.push({
      fixture: pair.fx.id,
      profile: pair.prof.name,
      mode: 'resume',
      curve_digest: digestR,
      band_drift: bands.band_drift,
      band_tail: bands.band_tail,
    });
  }
  writeJson(path.join(BASE, 'data/dur_k7.json'), dur);

  let ok = true;
  for (const pair of pairs) {
    const kid = `${pair.fx.id}:${pair.prof.name}`;
    const prof = pair.prof;
    const u = rows.find((r) => r.fixture === pair.fx.id && r.profile === pair.prof.name && r.mode === 'uninterrupted');
    const r = rows.find((x) => x.fixture === pair.fx.id && x.profile === pair.prof.name && x.mode === 'resume');
    if (!u || !r) { ok = false; continue; }
    if (u.curve_digest !== r.curve_digest) ok = false;
    if (u.band_drift > prof.band_max) ok = false;
    if (u.band_tail > prof.band_tail) ok = false;
    void kid;
  }

  const witness = {
    summary: {
      fixtures: ids,
      profiles: profiles.map((p) => p.name),
      pairs_run: pairs.length,
    },
    rows: rows.sort((a, b) => (a.fixture + a.profile + a.mode).localeCompare(b.fixture + b.profile + b.mode)),
  };
  writeJson(outPath, witness);
  process.exit(ok ? 0 : 1);
}

function main() {
  const args = parseArgs(process.argv);
  if (args.fullAudit) return fullAudit(args.outPath);
  console.log('usage: drv_k7.js --full-audit --out /app/output/resume_witness.json');
  process.exit(2);
}

main();
