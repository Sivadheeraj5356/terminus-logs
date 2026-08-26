import * as fs from "fs";
import { CollisionEpoch, CollisionLedger } from "../types";
import { payloadHash } from "../staging/write";

export function writeLedger(
  outPath: string,
  missionSlot: string,
  epochs: CollisionEpoch[],
  stagingDigest: string,
): CollisionLedger {
  const ledger: CollisionLedger = {
    mission_slot: missionSlot,
    epochs,
    total_collisions: epochs.length,
    staging_digest: stagingDigest,
    ledger_hash: "",
  };

  const envelope = {
    mission_slot: ledger.mission_slot,
    epochs: ledger.epochs,
    total_collisions: ledger.total_collisions,
    staging_digest: ledger.staging_digest,
  };
  ledger.ledger_hash = payloadHash(envelope);

  fs.writeFileSync(outPath, JSON.stringify(ledger, null, 2));
  return ledger;
}
