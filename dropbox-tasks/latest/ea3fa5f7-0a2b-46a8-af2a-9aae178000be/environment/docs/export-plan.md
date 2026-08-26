# export plan

Export stage reads validated staging artifacts and publishes resupply-plan.json plus utilization-report.json.

## Input files (read only)

- /app/state/tide-snapshot.json
- /app/state/rov-index.json
- /app/state/berth-staging.json
- /app/state/transfer-cert.json
- /app/state/export-bind.json
- /app/state/ingest-manifest.json
- /app/state/o2-priority-freeze.json

Export must not open cargo.jsonl, habitat.json, or any file under the mission directory. Read mission_label, rov_bays, and berth_ids from export-bind.json only.

## Preconditions (exit non-zero on failure)

publish_gate.sh enforces:

1. Required state files exist including transfer-cert.json
2. ingest-manifest bind_hash equals export-bind bind_hash
3. ingest-manifest rov_hash equals export-bind rov_hash and rov-index rov_hash
4. rov-index tide_hash equals tide-snapshot tide_hash
5. transfer-cert staging_hash equals berth-staging staging_hash and tide_hash matches
6. export-bind cert_hash equals transfer-cert cert_hash
7. berth-staging feasible is true
8. berth-staging cold_cap_ok is true (read from berth-staging.json)

## Output assembly

1. Build resupply plan lines from transfer-cert windows joined with rov-index slots and o2-priority-freeze entries (not berth-staging start/end/seq, not tide act o2) per resupply-plan-schema.md and transfer-cert.md
2. Plan staging_hash still comes from berth-staging.json; tide_hash from tide-snapshot.json
3. Write resupply-plan.json to /app/output
4. Build utilization report with berth_load dict and fingerprint from plan per utilization-report-schema.md
5. Write utilization-report.json to /app/output

## Determinism

Repeat export without re-ingest must produce byte-identical resupply-plan.json. utilization-report fingerprint must remain stable across repeat exports.
