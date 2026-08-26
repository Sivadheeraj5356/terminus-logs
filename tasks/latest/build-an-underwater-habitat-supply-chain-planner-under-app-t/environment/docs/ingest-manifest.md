# ingest manifest

Written to /app/state/ingest-manifest.json during ingest.

Records run metadata and bind alignment for export verification.

## Schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| mission_hash | string | From tide snapshot |
| bind_hash | string | Must match export-bind.json bind_hash |
| run_sequence | integer | Starts at 1, increments by 1 on each ingest |
| feasible | boolean | From export bind |
| cold_cap_ok | boolean | From export bind |
| rov_hash | string | From export bind |
| manifest_hash | string | SHA-256 hex digest (see below) |

## run_sequence

Each ingest increments run_sequence by 1 even when mission_hash is unchanged.

## manifest_hash

SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over schema_version, mission_hash, bind_hash, run_sequence, feasible, cold_cap_ok, and rov_hash. Exclude manifest_hash from digest input.

Export exits non-zero when manifest bind_hash does not match export-bind bind_hash.
