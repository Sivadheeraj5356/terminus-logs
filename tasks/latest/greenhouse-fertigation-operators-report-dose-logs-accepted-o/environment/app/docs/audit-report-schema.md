# Compliance audit report schema

Output path: /app/output/fertigation-compliance.json

Written JSON field order:

1. `greenhouse_id` (string)
2. `batches` (array, sorted by `batch_id` ascending)
3. `summary` (object)
4. `compliance_hash` (string)

Each batch object field order:

1. `batch_id`
2. `zone_id`
3. `dose_count`
4. `ec_drift_integral` (number)
5. `ec_ok`
6. `ph_ok`
7. `volume_ok`
8. `daily_volume_ok`
9. `batch_release_ok`

`summary` object:

| field | type |
|-------|------|
| batch_count | integer — CLOSED batches exported |
| released_count | integer — batches with batch_release_ok true |

Only CLOSED batches appear in `batches`. OPEN batches are omitted.

## compliance_hash

Let `payload = { greenhouse_id, batches, summary }` using the field values above (no `compliance_hash` key).

`compliance_hash` = lowercase SHA-256 hex digest of `json.Marshal(payload)` compact serialization (no added whitespace).

The written file includes `compliance_hash` as the fourth top-level field after `summary`. The on-disk report uses indented JSON for readability; the hash input is compact.
