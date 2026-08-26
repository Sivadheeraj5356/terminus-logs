import * as path from "path";
import * as fs from "fs";
import { loadManifest, loadBodies, loadFlares, catalogFingerprint } from "../ingest/load";
import { writeStagingEnvelope } from "../staging/write";

const catalogEnv = process.env.CASCADE_CATALOG_DIR;
const catalogDir =
  catalogEnv && path.isAbsolute(catalogEnv)
    ? catalogEnv
    : "/app/catalogs/leo-alpha";

const missionSlot = process.env.CASCADE_MISSION_SLOT || "";

const manifest = loadManifest(catalogDir);
if (missionSlot) {
  manifest.mission_slot = missionSlot;
}

const bodies = loadBodies(catalogDir);
const flares = loadFlares(catalogDir);
const fp = catalogFingerprint(catalogDir);

const stateDir = "/app/state";
fs.mkdirSync(stateDir, { recursive: true });

const staging = writeStagingEnvelope(
  path.join(stateDir, "cascade-staging.json"),
  manifest,
  bodies,
  flares,
  fp,
);

const seal = {
  catalog_fingerprint: fp,
  staging_hash: staging.staging_hash,
};
fs.writeFileSync(
  path.join(stateDir, "ingest-seal.json"),
  JSON.stringify(seal, null, 2),
);

console.log("Ingest complete:", staging.staging_hash);
