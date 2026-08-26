# berth staging

Written to /app/state/berth-staging.json during ingest.

## Assignment

Berth assignment runs during ingest. Ranking follows priority-ledger.md. Placement follows psi-gap-buffer.md including optional surge_cargo_id scheduling last. Cold totals follow cold-cap-policy.md. This document defines the staging artifact schema only.

## Final ordering

After every placement is made, including any surge_cargo_id row scheduled last, sort the assignment rows in ascending order first by start and then by cargo_id. Assign seq as a 1-based index in that final sorted order. The assignments array is written to berth-staging.json in this same order.

## Top-level schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| tide_hash | string | From tide-snapshot.json |
| assignments | array | Berth placement rows |
| feasible | boolean | True when all cargo placed within constraints |
| cold_m3_used | number | Sum of m3 for cold assignments, round 6 |
| cold_cap_ok | boolean | cold_m3_used <= cold_cap_m3 + 1e-9 |
| staging_hash | string | SHA-256 hex digest (see below) |

## assignment object

Required fields:

| Field | Type | Notes |
|-------|------|-------|
| cargo_id | string | |
| berth_id | string | |
| seq | integer | 1-based index after the final sort by start then cargo_id (see Final ordering) |
| gap_used | boolean | From psi gap logic |
| start | number | Round 6 |
| end | number | Round 6 |
| m3 | number | From tide act |
| cold | boolean | From tide act |

Optional field:

| Field | Type | Notes |
|-------|------|-------|
| surge | boolean | Present and true only for surge_cargo_id row |

Do not include priority_rank, o2, score, zone, psi, or transfer_min on assignment rows.

## staging_hash

SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over schema_version, tide_hash, assignments, feasible, cold_m3_used, and cold_cap_ok. Exclude staging_hash from digest input.

Export must read cold_cap_ok from this file, not from export-bind.json alone.
