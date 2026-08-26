# Atlas and ledger output schemas

## cascade-fragment-atlas.json

Written to /app/output/cascade-fragment-atlas.json by cascade-export.

Fields:
- mission_slot: string
- epoch_count: number of collision epochs that occurred
- final_body_count: number of surviving bodies at end of simulation
- bodies: array of body records, each with:
  - id: string
  - final_pos_m: {x, y, z} rounded to 6 decimal places
  - final_vel_mps: {x, y, z} rounded to 6 decimal places
  - mass_kg: number rounded to 6 decimal places
  - radius_m: number rounded to 6 decimal places
  - survived: boolean (true for all bodies present at end)
- atlas_hash: canonical JSON hash of {mission_slot, epoch_count, final_body_count, bodies}

## collision-epoch-ledger.json

Written to /app/output/collision-epoch-ledger.json by cascade-export.

Fields:
- mission_slot: string
- epochs: array of collision epoch records (see collision-spawn.md)
- total_collisions: number of epochs
- staging_digest: canonical JSON hash of {mission_slot, catalog_fingerprint} from the staging envelope
- ledger_hash: canonical JSON hash of {mission_slot, epochs, total_collisions, staging_digest}

All hashes use the same canonical JSON stringify described in staging-schema.md.
