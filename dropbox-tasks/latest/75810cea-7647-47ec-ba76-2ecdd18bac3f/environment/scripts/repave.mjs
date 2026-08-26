import { knitPlan } from '../tools/weave.mjs';
import { fillCask } from '../tools/cask.mjs';
import { contentDigestOf } from '../tools/hash.mjs';
import { writePlanGraph, writeLockAndManifests } from '../tools/emit.mjs';
import { appendLedger, readLedger, writeLedger } from '../tools/ledger.mjs';
import { writeJson } from '../tools/json.mjs';

const root = process.cwd();
const plan = knitPlan(root);
const peerMap = plan.peerMap || new Map();
for (const pkg of plan.packages) {
  const peers = peerMap.get(pkg.name) || [];
  const payload = {
    name: pkg.name,
    version: pkg.version,
    path: pkg.path,
    peers,
    markers: { sealed: true },
  };
  pkg.contentDigest = contentDigestOf(payload);
  pkg.payload = payload;
}
writePlanGraph(root, plan);
writeLockAndManifests(root, plan);
fillCask(root, plan);
writeJson(`${root}/state/active-train.json`, {
  id: plan.train.id,
  epoch: plan.train.epoch,
});
const journal = `${root}/state/migrate-journal.jsonl`;
const events = readLedger(journal);
const tip = events[events.length - 1];
if (!tip || tip.phase !== 'COMMIT' || tip.fingerprint !== plan.fingerprint) {
  appendLedger(journal, { phase: 'SNAPSHOT', fingerprint: plan.fingerprint });
  appendLedger(journal, {
    phase: 'STAGE',
    keys: plan.packages.map((pkg) => `${pkg.name}@${pkg.version}`),
  });
  appendLedger(journal, { phase: 'PROMOTE', train: plan.train.id });
  appendLedger(journal, { phase: 'COMMIT', fingerprint: plan.fingerprint });
}
console.log(JSON.stringify({ sealed: true, fingerprint: plan.fingerprint, train: plan.train }));
