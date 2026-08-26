# resupply plan schema

Written to /app/output/resupply-plan.json during export.

Built only from staging state files. Do not re-read cargo.jsonl.

## Top-level schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| mission_label | string | From export-bind.json mission_label |
| lines | array | One row per berth assignment |
| tide_hash | string | From tide-snapshot.json |
| staging_hash | string | From berth-staging.json |

## line object

| Field | Type | Notes |
|-------|------|-------|
| cargo_id | string | |
| berth_id | string | |
| seq | integer | From assignment |
| start | number | From assignment |
| end | number | From assignment |
| rov_id | string or null | From rov-index slot when needs_rov, else null |
| surge | boolean | From assignment surge field, default false |
| o2 | integer | From tide act matching cargo_id |

Lines follow assignment order (same count as assignments when feasible).

The utilization report fingerprint is computed from this plan object, not from the report itself.
