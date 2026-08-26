import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { readJson, writeJson } from '../tools/json.mjs';
import { contentDigestOf, sha256Bytes } from '../tools/hash.mjs';
import { knitPlan } from '../tools/weave.mjs';

const root = process.cwd();
const errors = [];
const plan = knitPlan(root);
const peerMap = plan.peerMap || new Map();
for (const pkg of plan.packages) {
  const peers = peerMap.get(pkg.name) || [];
  pkg.payload = {
    name: pkg.name,
    version: pkg.version,
    path: pkg.path,
    peers,
    markers: { sealed: true },
  };
  pkg.contentDigest = contentDigestOf(pkg.payload);
}
const graph = readJson(`${root}/generated/plan-graph.json`);
const store = readJson(`${root}/offline-store/index.json`);
if (graph.schema !== 'migrate-plan-graph-v1') errors.push('plan-schema');
if (store.schema !== 'migrate-store-index-v1') errors.push('store-schema');
if (graph.fingerprint !== plan.fingerprint) errors.push('fingerprint-mismatch');
if (graph.train !== plan.train.id || Number(graph.epoch) !== Number(plan.train.epoch)) {
  errors.push('train-mismatch');
}
if (JSON.stringify(graph.importers) !== JSON.stringify(plan.importers)) errors.push('importer-mismatch');
if (JSON.stringify(graph.peers) !== JSON.stringify(plan.peers)) errors.push('peer-mismatch');

const wantKeys = new Set(
  plan.packages.map((pkg) => `${pkg.name}@${pkg.version}#${pkg.contentDigest.slice(0, 16)}`)
);
const gotKeys = new Set(Object.keys(store.packages || {}));
for (const key of wantKeys) if (!gotKeys.has(key)) errors.push(`missing-key:${key}`);
for (const key of gotKeys) if (!wantKeys.has(key)) errors.push(`ghost-key:${key}`);

for (const pkg of plan.packages) {
  const key = `${pkg.name}@${pkg.version}#${pkg.contentDigest.slice(0, 16)}`;
  const record = store.packages[key];
  if (!record) continue;
  if (!existsSync(`${root}/${record.tarball}`)) {
    errors.push(`missing-tarball:${key}`);
    continue;
  }
  const body = readFileSync(`${root}/${record.tarball}`);
  if (sha256Bytes(body) !== record.sha256) errors.push(`sha-mismatch:${key}`);
  const payload = JSON.parse(body.toString('utf8'));
  if (JSON.stringify(payload) !== JSON.stringify(pkg.payload)) errors.push(`payload-mismatch:${key}`);
  if (!payload.markers?.sealed) errors.push(`unsealed:${key}`);
}

writeJson(`${root}/reports/seal-audit.json`, {
  schema: 'migrate-audit-v1',
  fingerprint: plan.fingerprint,
  train: plan.train.id,
  epoch: plan.train.epoch,
  errors,
});
if (errors.length) {
  console.error(JSON.stringify({ ok: false, errors }));
  process.exit(1);
}
console.log(JSON.stringify({ ok: true, errors: [] }));
