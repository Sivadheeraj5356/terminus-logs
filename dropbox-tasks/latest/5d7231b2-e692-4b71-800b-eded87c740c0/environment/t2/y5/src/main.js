#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { readFrame, runUninterrupted, curveBytes, fnv1a32 } = require('../../../n4/q7/src/LoopM3');
const { catalog_d } = require('./CatalogD');

const ENV = process.env.APP_ROOT || '/app';
const BASE = path.join(ENV, 'environment');
const OUT = path.join(ENV, 'output');
const TRACE = path.join(OUT, 'traces');
const STAGE = path.join(OUT, 'stage');

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

function loadConfig() {
  const lim = readTomlPairs(path.join(BASE, 'data/lim_k7.toml'));
  const holdText = fs.readFileSync(path.join(BASE, 'data/hold_q3.toml'), 'utf8');
  const hold = [];
  let cur = null;
  for (const raw of holdText.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    if (line === '[[hold]]') { if (cur) hold.push(cur); cur = {}; continue; }
    const m = line.match(/^([a-z_]+)\s*=\s*(.+)$/);
    if (!m || !cur) continue;
    let val = m[2].trim().replace(/^"|"$/g, '');
    if (val === 'true' || val === 'false') cur[m[1]] = val === 'true';
    else cur[m[1]] = val;
  }
  if (cur) hold.push(cur);
  const ids = fs.readFileSync(path.join(BASE, 'guide/id_list.txt'), 'utf8')
    .split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  return { ...lim, hold, ids };
}

function framePath(name) {
  return path.join(BASE, 'fixtures/frames', name);
}

function readJson(p, fb) {
  if (!fs.existsSync(p)) return fb;
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function writeJson(p, obj) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(obj, null, 2) + '\n');
}

async function phaseWarm() {
  const cfg = loadConfig();
  const snap = { probe_green: true, rows: {} };
  for (const fx of cfg.fixtures) {
    if (!cfg.ids.includes(fx.id)) continue;
    const frame = readFrame(fs.readFileSync(framePath(fx.frame)));
    const prof = cfg.profiles[0];
    const curve = runUninterrupted(frame, prof);
    const body = curveBytes(curve);
    snap.rows[`${fx.id}:${prof.name}`] = { hex: fnv1a32(body), ready: true };
  }
  writeJson(path.join(BASE, 'data/snap_k7.json'), snap);
  fs.mkdirSync(STAGE, { recursive: true });
  writeJson(path.join(STAGE, 'headline.json'), { ok: true, rows: snap.rows });
}

async function phaseTrainBase() {
  fs.mkdirSync(OUT, { recursive: true });
  writeJson(path.join(OUT, '.phase'), { last: 'train-base' });
}

async function phasePauseStore() {
  const dur = readJson(path.join(BASE, 'data/dur_k7.json'), { rows: {} });
  writeJson(path.join(BASE, 'data/dur_k7.json'), dur);
  writeJson(path.join(OUT, '.phase'), { last: 'pause-store' });
}

async function phaseTrainContinue() {
  writeJson(path.join(OUT, '.phase'), { last: 'train-continue' });
}

async function main() {
  const phase = process.argv[2] || 'warm-probe';
  if (phase === 'warm-probe') return phaseWarm();
  if (phase === 'train-base') return phaseTrainBase();
  if (phase === 'pause-store') return phasePauseStore();
  if (phase === 'train-continue') return phaseTrainContinue();
  if (phase === 'catalog') {
    const cfg = loadConfig();
    console.log(catalog_d(cfg.ids).join(','));
    return;
  }
  throw new Error('unknown phase: ' + phase);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
