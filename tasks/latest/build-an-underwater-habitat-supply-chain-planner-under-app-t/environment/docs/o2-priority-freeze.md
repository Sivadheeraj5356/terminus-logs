# o2 priority freeze

During ingest, after priority ledger ranking is computed, write /app/state/o2-priority-freeze.json capturing the oxygen tier order used for berth assignment.

## schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| tide_hash | string | tide_hash from tide-snapshot.json at freeze time |
| entries | array | One row per ranked cargo in ledger order |

Each entry contains cargo_id (string) and o2 (integer) copied from the ranked act. The ledger order includes every cargo, including the surge_cargo_id cargo when defined, so the freeze holds one entry for each exported plan line even though berth assignment schedules the surge cargo last.

## freeze_hash

SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over schema_version, tide_hash, and entries. Exclude freeze_hash from digest input.

## export validation

Export publish_gate must reject when freeze_hash does not match the digest of schema_version, tide_hash, and entries. Export publish must also reject when any resupply-plan.json line o2 value does not match the frozen entry for the same cargo_id. Export reads only /app/state artifacts and must not re-open mission inputs.
