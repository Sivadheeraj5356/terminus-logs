# Readiness report

Written by `assess` to `--output-report`.

Top-level fields:

- digests: `facility_digest`, `catalog_digest`, `maintenance_digest`, `inventory_digest`, `report_digest`
- `vessels` — copied from the inventory stage vessel rows
- `placements` — one row per placement request
- counters: `ready_vessel_count`, `blocked_vessel_count`, `satisfied_placement_count`, `placement_request_count`

## Placement assignment

Specimen compatibility requires exact equality of `specimen_class` and vessel `cryogen_class`.

A vessel meets a request when it is `ready`, compatible, and `hold_hours >= min_hold_hours`.

If `preferred_vessel_id` is non-empty:

1. If that vessel is missing → reason `preferred_vessel_missing`
2. Else if it does not meet the request → reason `preferred_vessel_not_eligible`
3. Else assign the preferred vessel and clear reasons

If not yet satisfied, assign the lexicographically first eligible vessel (stage order is already sorted by `vessel_id`). If none exist, add `no_compatible_ready_vessel`.

When preferred was ineligible but a fallback vessel is assigned, keep the preferred reason and set `satisfied=true`.

`report_digest` hashes the canonical compact JSON of all report fields except `report_digest`.
