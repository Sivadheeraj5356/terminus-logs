# ROV lead time

Written to /app/state/rov-index.json during ingest.

## Slot reservation

Process tide snapshot acts where needs_rov is true, sorted by (berth_start, cargo_id).

Eligible bays are all bays except those listed in rov_bays_offline (see rov-bays-offline.md). When rov_bays_offline is absent or empty, every bay is eligible.

For each act:

1. need = berth_start - rov_lead_min
2. Pick an eligible bay index i (0-based) minimizing (max(free[i], need), i) where free tracks bay availability
3. start = max(free[pick], need), rounded to six decimals
4. end = berth_start, rounded to six decimals
5. free[pick] = end + rov_turn_min
6. rov_id = R followed by one-based bay number (R1, R2, R3, ...)

## rov-index.json schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| tide_hash | string | From tide-snapshot.json |
| slots | array | ROV reservations |
| rov_hash | string | SHA-256 hex digest (see below) |

## slot object (exactly 4 fields, no extras)

| Field | Type |
|-------|------|
| cargo_id | string |
| rov_id | string |
| start | number |
| end | number |

Do not include lead_min, turn_min, bay, berth_start, late, or other derived fields in slots.

## rov_hash

SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over schema_version, tide_hash, and slots. Exclude rov_hash from digest input.
