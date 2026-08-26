#!/usr/bin/env bash
set -euo pipefail
cd /app

cat > tools/weave.mjs <<'EOF'
import { readJson } from './json.mjs';
import { sha256Text } from './hash.mjs';

function activeTrain(trainsDoc) {
  const open = (trainsDoc.trains || []).filter((train) => train.status === 'open');
  open.sort((a, b) => Number(b.epoch) - Number(a.epoch) || String(a.id).localeCompare(String(b.id)));
  if (!open.length) throw new Error('no open train');
  return open[0];
}

function eligibleCandidates(pin, train) {
  return (pin.candidates || []).filter((candidate) => {
    const minOk = Number(candidate.minTrainEpoch) <= Number(train.epoch);
    const max = candidate.maxTrainEpoch;
    const maxOk = max === undefined || max === null || Number(train.epoch) <= Number(max);
    const channelOk = (train.channels || []).includes(candidate.channel);
    return minOk && maxOk && channelOk;
  });
}

function pickPackage(pin, binding, train) {
  const eligible = eligibleCandidates(pin, train);
  if (!eligible.length) throw new Error(`no eligible candidate for pin`);
  const byHint = eligible.filter((candidate) => candidate.channel === binding.channelHint);
  const pool = byHint.length
    ? byHint
    : eligible.filter((candidate) => candidate.channel === pin.defaultChannel);
  const finalPool = pool.length ? pool : eligible;
  finalPool.sort((a, b) => String(a.package).localeCompare(String(b.package)));
  return finalPool[0].package;
}

export function knitPlan(root = process.cwd()) {
  const catalog = readJson(`${root}/config/catalog.json`);
  const hosts = readJson(`${root}/config/migrate-hosts.json`);
  const trainsDoc = readJson(`${root}/config/release-trains.json`);
  const extensions = readJson(`${root}/config/extensions.json`);
  const byName = new Map(catalog.packages.map((pkg) => [pkg.name, pkg]));
  const train = activeTrain(trainsDoc);

  const importers = {};
  const used = new Map();

  for (const host of hosts.hosts) {
    const edges = {};
    for (const [alias, binding] of Object.entries(host.bindings)) {
      const pin = catalog.pins[alias];
      if (!pin) throw new Error(`missing pin ${alias}`);
      const chosen = pickPackage(pin, binding, train);
      const pkg = byName.get(chosen);
      if (!pkg) throw new Error(`missing package ${chosen}`);
      edges[alias] = `workspace:${pkg.name}@*`;
      used.set(pkg.name, pkg);
    }
    importers[host.importer] = Object.fromEntries(
      Object.keys(edges).sort().map((key) => [key, edges[key]])
    );
  }

  const peerMap = new Map();
  const peers = new Set();
  for (const name of [...used.keys()]) {
    for (const extension of extensions.extensions || []) {
      if (extension.whenPackage !== name) continue;
      const required = [...(extension.peerRequires || [])].sort();
      peerMap.set(name, required);
      for (const peer of required) {
        peers.add(peer);
        if (!used.has(peer)) {
          const pkg = byName.get(peer);
          if (!pkg) throw new Error(`missing peer ${peer}`);
          used.set(peer, pkg);
        }
      }
    }
  }
  for (const name of used.keys()) {
    if (!peerMap.has(name)) peerMap.set(name, []);
  }

  const packages = [...used.values()].sort((a, b) => a.name.localeCompare(b.name));
  const peerList = [...peers].sort();
  const bindParts = [];
  for (const importer of Object.keys(importers).sort()) {
    for (const alias of Object.keys(importers[importer]).sort()) {
      const target = importers[importer][alias].slice('workspace:'.length).split('@*')[0];
      bindParts.push(`${importer}:${alias}=${target}`);
    }
  }
  const fingerprint = sha256Text(
    `binds=${bindParts.join(';')}|peers=${peerList.join(',')}|train=${train.id}@${train.epoch}`
  );
  return {
    train,
    fingerprint,
    packages,
    importers,
    peers: peerList,
    catalogByName: byName,
    peerMap,
  };
}
EOF

cat > tools/cask.mjs <<'EOF'
import { mkdirSync, writeFileSync, rmSync, existsSync, readdirSync } from 'node:fs';
import { writeJson } from './json.mjs';
import { contentDigestOf, sha256Bytes } from './hash.mjs';

function tarballName(pkg) {
  return `${pkg.path.split('/').pop()}-${pkg.version}.json`;
}

export function fillCask(root, plan) {
  mkdirSync(`${root}/offline-store/tarballs`, { recursive: true });
  const next = {};
  const keep = new Set();
  for (const pkg of plan.packages) {
    const peers = (plan.peerMap && plan.peerMap.get(pkg.name)) || pkg.payload?.peers || [];
    const payload = pkg.payload || {
      name: pkg.name,
      version: pkg.version,
      path: pkg.path,
      peers: [...peers].sort(),
      markers: { sealed: true },
    };
    const digest = pkg.contentDigest || contentDigestOf(payload);
    const body = Buffer.from(JSON.stringify(payload, null, 2) + String.fromCharCode(10));
    const rel = `offline-store/tarballs/${tarballName(pkg)}`;
    writeFileSync(`${root}/${rel}`, body);
    keep.add(tarballName(pkg));
    const key = `${pkg.name}@${pkg.version}#${digest.slice(0, 16)}`;
    next[key] = {
      name: pkg.name,
      version: pkg.version,
      path: pkg.path,
      tarball: rel,
      sha256: sha256Bytes(body),
      bytes: body.length,
      contentDigest: digest,
    };
  }
  const tarDir = `${root}/offline-store/tarballs`;
  if (existsSync(tarDir)) {
    for (const name of readdirSync(tarDir)) {
      if (!keep.has(name)) rmSync(`${tarDir}/${name}`, { force: true });
    }
  }
  const index = { schema: 'migrate-store-index-v1', packages: next };
  writeJson(`${root}/offline-store/index.json`, index);
  return index;
}
EOF

cat > scripts/reseat.mjs <<'EOF'
import { readLedger, writeLedger, appendLedger, lastCommitIndex } from '../tools/ledger.mjs';

export function parkTip(root = process.cwd()) {
  const path = `${root}/state/migrate-journal.jsonl`;
  const events = readLedger(path);
  const idx = lastCommitIndex(events);

  if (idx >= 0 && idx < events.length - 1) {
    const incomplete = events.slice(idx + 1);
    if (incomplete.some((event) => event.phase === 'ABORT')) {
      console.log(JSON.stringify({ resumed: false, mode: 'already-marked' }));
      return;
    }
    writeLedger(path, events.slice(0, idx + 1));
    appendLedger(path, {
      phase: 'ABORT',
      reason: 'interrupted_train_migrate',
      dropped: incomplete.map((event) => event.phase),
    });
    console.log(JSON.stringify({ resumed: true, mode: 'append-abort', dropped: incomplete.length }));
    return;
  }
  console.log(JSON.stringify({ resumed: false, mode: 'noop' }));
}

parkTip();
EOF

/app/tools/pnpm run verify:all
