# export bind

Written to /app/state/export-bind.json during ingest.

Captures export metadata frozen at ingest time and links mission hashes to validated staging artifacts including transfer certification.

## Schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| mission_hash | string | From tide snapshot |
| tide_hash | string | From tide snapshot |
| staging_hash | string | From berth staging |
| cert_hash | string | From transfer-cert.json |
| feasible | boolean | From berth staging |
| cold_cap_ok | boolean | From berth staging |
| cold_m3_used | number | From berth staging |
| mission_label | string | From habitat mission_label at ingest |
| rov_bays | integer | From habitat rov_bays at ingest |
| berth_ids | array | Sorted lexicographic berth_id strings from habitat berths at ingest |
| rov_hash | string | From rov-index.json at ingest |
| bind_hash | string | SHA-256 hex digest (see below) |

## bind_hash

SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over schema_version, mission_hash, tide_hash, staging_hash, cert_hash, feasible, cold_cap_ok, cold_m3_used, mission_label, rov_bays, berth_ids, and rov_hash. Exclude bind_hash from digest input.

publish_gate.sh verifies rov_hash matches rov-index.json and cert_hash matches transfer-cert.json before export_plan runs.

Export verifies ingest-manifest bind_hash matches export-bind bind_hash before publishing. Export reads mission_label, rov_bays, and berth_ids from this file, not from habitat.json.
