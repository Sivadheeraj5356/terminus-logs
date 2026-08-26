# Hypersonic fragment cascade epoch atlas

Build a Kessler-style orbital debris cascade forecasting system on the working TypeScript simulation library at /app. The system must ingest debris body catalogs, propagate Keplerian orbits with atmospheric drag under solar-flare density modulation, detect sphere-sphere collisions, spawn momentum-and-energy-conserving fragment clouds, and export a cascade fragment atlas with a collision epoch ledger.

## Contract sources

All behavior, JSON field schemas, integrator constants, collision rules, drag model, hash conventions, and export contracts are defined in /app/docs/cli.md, /app/docs/staging-schema.md, /app/docs/kepler-integrator.md, /app/docs/collision-spawn.md, /app/docs/drag-flare.md, /app/docs/atlas-ledger-schema.md, /app/docs/export-sequence.md, and /app/docs/canonical-json-hash.md. Those documents govern every field name, array order, hash seal, and cross-artifact binding tested by the verifier.

## cascade-ingest obligations

1. Read the catalog directory (default /app/catalogs/leo-alpha; honor CASCADE_CATALOG_DIR when set to an absolute path).
2. Load bodies from bodies.jsonl in feed order (line by line, preserving the sequence they appear in the file). Do not sort by id or any other field.
3. Honor the per-body cd field from the catalog; if absent default to 2.2.
4. Load flare events from flares.jsonl sorted by t_sec ascending.
5. Compute catalog_fingerprint as sha256 of concatenated raw bodies.jsonl bytes then raw flares.jsonl bytes.
6. Write /app/state/cascade-staging.json per staging-schema.md with staging_hash computed using canonical JSON hashing per canonical-json-hash.md (set staging_hash to empty string before hashing the envelope, then write the digest back).
7. Write /app/state/ingest-seal.json with catalog_fingerprint and staging_hash.
8. Honor CASCADE_MISSION_SLOT override for the mission_slot label.

## cascade-export obligations

1. Refuse to run when /app/state/cascade-staging.json is missing, /app/state/ingest-seal.json is missing, or the seal staging_hash does not match the staging file.
2. Propagate all bodies using the RK2 midpoint integrator specified in kepler-integrator.md. The acceleration model combines central gravity and atmospheric drag including the solar-flare density_scale from drag-flare.md.
3. After each integration step, detect collisions per collision-spawn.md. Process at most one collision per timestep; if multiple pairs qualify, pick the lexicographically smallest (id_a, id_b) pair.
4. Spawn fragments conserving both total momentum and total kinetic energy as described in collision-spawn.md. Record each collision as an epoch with residuals.
5. Write /app/output/cascade-fragment-atlas.json per atlas-ledger-schema.md with all positions and velocities rounded to 6 decimal places on export.
6. Write /app/output/collision-epoch-ledger.json per atlas-ledger-schema.md. The staging_digest field is the canonical hash of the mission_slot and catalog_fingerprint from the staging envelope.
7. Write /app/state/export-sequence.json per export-sequence.md with monotonic run_seq. Re-running on unchanged inputs must leave atlas_hash stable while incrementing run_seq.
8. The decoy module at /app/src/decoy/wrap.ts must not be imported on the export hot path.
