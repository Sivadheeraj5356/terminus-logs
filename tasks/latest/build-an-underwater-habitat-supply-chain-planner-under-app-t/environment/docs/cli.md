# CLI

## habitat-resupply-ingest

Usage: habitat-resupply-ingest [MISSION_DIR]

Reads cargo.jsonl and habitat.json from a mission directory and writes all seven ingest state files under /app/state.

Mission directory resolution (first match wins):

1. RESUPPLY_MISSION_DIR environment variable when set
2. First positional argument when provided
3. Default /app/data/mission

The resolved path must be absolute. Relative paths exit non-zero.

Outputs written on success:

- /app/state/tide-snapshot.json
- /app/state/rov-index.json
- /app/state/berth-staging.json
- /app/state/transfer-cert.json
- /app/state/export-bind.json
- /app/state/o2-priority-freeze.json
- /app/state/ingest-manifest.json

Re-running ingest on unchanged cargo input keeps mission_hash stable and increments run_sequence on ingest-manifest.json.

Ingest algorithms and schemas: tide-snapshot.md, tide-offset-windows.md, berth-clock-band.md, lane-window-offset.md, wave-scaling.md, wave-buffer.md, rov-lead-time.md, priority-ledger.md, psi-gap-buffer.md, cold-cap-policy.md, berth-staging.md, transfer-cert.md, o2-priority-freeze.md, export-bind.md, ingest-manifest.md, habitat-profile.md, cargo-jsonl-format.md.

## habitat-resupply-export

Usage: habitat-resupply-export

Reads only validated staging artifacts under /app/state. Must not open cargo.jsonl, habitat.json, or any path under the mission directory during export.

Required inputs:

- tide-snapshot.json
- rov-index.json
- berth-staging.json
- transfer-cert.json
- export-bind.json
- ingest-manifest.json
- o2-priority-freeze.json

Export exits non-zero when any staging file is missing, bind_hash on ingest-manifest does not match export-bind, cert_hash on export-bind does not match transfer-cert, feasible is false on berth-staging, or cold_cap_ok is false on berth-staging.json (not export-bind alone).

Outputs on success:

- /app/output/resupply-plan.json
- /app/output/utilization-report.json

Re-running export on unchanged validated staging must yield byte-identical resupply-plan.json and a stable fingerprint on utilization-report.json.

Export assembly: export-plan.md, resupply-plan-schema.md, utilization-report-schema.md.
