import * as fs from "fs";
import * as path from "path";
import { StagingEnvelope, Body, CollisionEpoch, ExportSequence } from "../types";
import { propagateStep } from "../kepler/propagate";
import { detectCollision } from "../collision/detect";
import { spawnFragments } from "../spawn/fragments";
import { currentDensityScale } from "../drag/flare";
import { writeAtlas } from "../export/atlas";
import { writeLedger } from "../export/ledger";
import { payloadHash } from "../staging/write";

const stateDir = "/app/state";
const outputDir = "/app/output";

fs.mkdirSync(outputDir, { recursive: true });

const stagingPath = path.join(stateDir, "cascade-staging.json");
const sealPath = path.join(stateDir, "ingest-seal.json");

if (!fs.existsSync(stagingPath) || !fs.existsSync(sealPath)) {
  console.error("Staging or seal missing. Run cascade-ingest first.");
  process.exit(1);
}

const staging: StagingEnvelope = JSON.parse(
  fs.readFileSync(stagingPath, "utf-8"),
);
const seal = JSON.parse(fs.readFileSync(sealPath, "utf-8"));

if (seal.staging_hash !== staging.staging_hash) {
  console.error("Stale seal — staging_hash mismatch.");
  process.exit(1);
}

const dt = staging.manifest.dt_sec;
const horizon = staging.manifest.horizon_sec;
const steps = Math.ceil(horizon / dt);
const fragmentCount = staging.manifest.fragment_count;
const minSep = staging.manifest.min_sep_m;

let bodies: Body[] = JSON.parse(JSON.stringify(staging.bodies));
const epochs: CollisionEpoch[] = [];

for (let step = 0; step < steps; step++) {
  const t = step * dt;
  const ds = currentDensityScale(staging.flares, t);

  for (const b of bodies) {
    propagateStep(b, dt, ds);
  }

  const pair = detectCollision(bodies);
  if (pair) {
    const a = bodies[pair.i];
    const b2 = bodies[pair.j];
    const result = spawnFragments(a, b2, fragmentCount, minSep, t);
    bodies = bodies.filter((_, idx) => idx !== pair.i && idx !== pair.j);
    bodies.push(...result.fragments);
    epochs.push(result.epoch);
  }
}

const stagingDigest = payloadHash({
  mission_slot: staging.mission_slot,
  catalog_fingerprint: staging.catalog_fingerprint,
});

const atlas = writeAtlas(
  path.join(outputDir, "cascade-fragment-atlas.json"),
  staging.mission_slot,
  bodies,
  epochs.length,
);

const ledger = writeLedger(
  path.join(outputDir, "collision-epoch-ledger.json"),
  staging.mission_slot,
  epochs,
  stagingDigest,
);

const seqPath = path.join(stateDir, "export-sequence.json");
let seq: ExportSequence = { run_seq: 0, atlas_hash: "", ledger_hash: "" };
if (fs.existsSync(seqPath)) {
  seq = JSON.parse(fs.readFileSync(seqPath, "utf-8"));
}
seq.run_seq += 1;
seq.atlas_hash = atlas.atlas_hash;
seq.ledger_hash = ledger.ledger_hash;
fs.writeFileSync(seqPath, JSON.stringify(seq, null, 2));

console.log("Export complete:", atlas.atlas_hash, ledger.ledger_hash);
