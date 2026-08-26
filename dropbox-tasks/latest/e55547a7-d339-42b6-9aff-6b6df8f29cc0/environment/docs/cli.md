# CLI reference

## cascade-ingest

Reads a debris catalog directory and writes a staging snapshot.

Catalog directory: honor CASCADE_CATALOG_DIR when set to an absolute path; otherwise default to /app/catalogs/leo-alpha.

Input files within the catalog directory:
- manifest.json — mission parameters (mission_slot, dt_sec, horizon_sec, fragment_count, min_sep_m)
- bodies.jsonl — one JSON object per line; each body has id, mass_kg, radius_m, pos_m {x,y,z}, vel_mps {x,y,z}, and optional cd (default 2.2)
- flares.jsonl — one JSON object per line; each flare event has t_sec and density_scale

Bodies must be loaded in feed order (the order they appear in bodies.jsonl). Do not sort by id or any other field.

If CASCADE_MISSION_SLOT is set, override the manifest mission_slot with that value.

Output:
- /app/state/cascade-staging.json — staging envelope per staging-schema.md
- /app/state/ingest-seal.json — catalog_fingerprint and staging_hash for export validation

## cascade-export

Reads the staging snapshot, runs the Keplerian cascade simulation, and writes output files.

Refuse to run when:
- /app/state/cascade-staging.json is missing
- /app/state/ingest-seal.json is missing
- staging_hash in the seal does not match the staging file

Simulation uses the physics described in kepler-integrator.md, collision-spawn.md, and drag-flare.md.

Output:
- /app/output/cascade-fragment-atlas.json — per atlas-ledger-schema.md
- /app/output/collision-epoch-ledger.json — per atlas-ledger-schema.md
- /app/state/export-sequence.json — per export-sequence.md

Re-running on unchanged inputs must leave atlas_hash unchanged while still incrementing run_seq.

The decoy module at /app/src/decoy/wrap.ts must NOT be imported or called anywhere on the export hot path.
