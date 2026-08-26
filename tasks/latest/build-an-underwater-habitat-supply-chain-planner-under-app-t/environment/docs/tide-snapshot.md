# tide snapshot

Written to /app/state/tide-snapshot.json during ingest.

## Top-level schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| mission_hash | string | SHA-256 hex from habitat-profile.md |
| acts | array | One entry per cargo row |
| tide_hash | string | SHA-256 hex digest (see below) |

## act object (exactly these 14 fields, no extras)

Each act contains only:

| Field | Type | Source / formula |
|-------|------|------------------|
| cargo_id | string | cargo row |
| dock_min | number | cargo row |
| tide_ms | integer | cargo row, signed |
| berth_start | number | dock_min + tide_ms/60000, round 6, then optional clock adjustments in tide-offset-windows.md |
| transfer_min | number | base_min * wave_m, round 6, then optional wave buffer in wave-buffer.md |
| berth_end | number | berth_start + transfer_min, round 6, recomputed after each adjustment |
| psi | number | cargo row |
| wave_m | number | cargo row |
| score | number | priority - wave_m*2 - abs(tide_ms)/60000, round 6 |
| lane | string | cargo row |
| needs_rov | boolean | needs_rov OR lane != primary_lane |
| m3 | number | cargo row |
| cold | boolean | cargo row |
| o2 | integer | cargo row |

Do not include zone, base_min, priority, or other cargo-only fields in acts.

## tide_hash

Compute tide_hash as SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over the object containing schema_version, mission_hash, and acts only. The tide_hash field itself is excluded from the digest input.
