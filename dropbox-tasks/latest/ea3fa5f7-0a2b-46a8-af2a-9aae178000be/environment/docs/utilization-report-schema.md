# utilization report schema

Written to /app/output/utilization-report.json during export.

## Top-level schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| rov_bays | integer | From export-bind.json rov_bays |
| cold_m3_used | number | From berth-staging.json |
| berth_load | object | Map berth_id to assignment count |
| fingerprint | string | SHA-256 hex of resupply-plan.json body |

## berth_load

Object (dict) mapping each habitat berth_id to the count of resupply plan lines assigned to that berth.

Example shape:

```
{"north-dock": 5, "south-bay": 3}
```

Do not use berth_utilization arrays, berths lists, or other key names. The field must be named berth_load.

Include every berth_id from export-bind.json berth_ids even when count is zero.

## fingerprint

Compute fingerprint as SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over the complete resupply-plan.json object (schema_version, mission_label, lines, tide_hash, staging_hash).

The fingerprint digests the plan, not the utilization report.

Re-export on unchanged staging must produce the same fingerprint.
