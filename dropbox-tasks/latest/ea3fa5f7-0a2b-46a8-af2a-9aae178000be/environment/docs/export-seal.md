# export seal

After a successful export publish, write /app/state/export-seal.json recording the frozen bind and plan fingerprint for the run.

## When to write

Export stage writes the seal only after resupply-plan.json and utilization-report.json are written and all publish_gate checks pass.

## Schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| run_sequence | integer | From ingest-manifest.json at publish time |
| bind_hash | string | From export-bind.json |
| rov_hash | string | From export-bind.json |
| plan_fingerprint | string | utilization-report.json fingerprint field |

## seal_hash

SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over schema_version, run_sequence, bind_hash, rov_hash, and plan_fingerprint. Exclude seal_hash from digest input.

Repeat export without re-ingest must leave export-seal.json byte-identical. Re-ingest increments run_sequence in ingest-manifest but does not update the seal until the next successful export.
