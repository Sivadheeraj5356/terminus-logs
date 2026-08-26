# transfer certification

Written to /app/state/transfer-cert.json during ingest after berth-staging.json is final and before export-bind.json is frozen.

Berth staging records placement geometry. Transfer certification is a separate certified window layer that export must consume. Export must not copy start, end, or seq from berth-staging.json into resupply-plan.json.

## Handoff padding

Optional habitat field handoff_pad_min (number, minutes). When absent, treat as 0.

Build certified windows from berth-staging assignments:

1. Start from each assignment row (cargo_id, berth_id, start, end, gap_used, surge when present).
2. For each berth_id, order rows by ascending start then cargo_id.
3. Walk consecutive pairs on that berth. Apply handoff padding only when the later row has gap_used true and handoff_pad_min is greater than 0. In that case, add handoff_pad_min to that later row start, then set end to start plus the prior transfer duration (end minus start before the pad). Round start and end to six decimals. Mark handoff true on that window.
4. After every berth walk finishes, sort all windows globally by ascending start then cargo_id and assign seq as a 1-based index in that order.

handoff is true only when gap_used is true and handoff_pad_min is greater than 0. When handoff_pad_min is 0, handoff stays false on every window, certified start and end match berth-staging, and the transfer-cert artifact must still be written so export can read it.

## Schema

| Field | Type | Notes |
|-------|------|-------|
| schema_version | integer | Must be 1 |
| tide_hash | string | From berth-staging |
| staging_hash | string | From berth-staging |
| windows | array | Certified transfer windows |
| cert_hash | string | Digest below |

Each window object:

| Field | Type | Notes |
|-------|------|-------|
| cargo_id | string | |
| berth_id | string | |
| seq | integer | After global sort |
| start | number | Round 6 |
| end | number | Round 6 |
| handoff | boolean | True only when gap_used is true and handoff_pad_min is greater than 0 |

## cert_hash

SHA-256 hex of compact JSON (separators comma-colon, sort_keys true) over schema_version, tide_hash, staging_hash, and windows. Exclude cert_hash from the digest input.

## Export binding

export-bind.json must freeze cert_hash from transfer-cert.json. publish_gate must reject when transfer-cert staging_hash does not match berth-staging staging_hash, when tide_hash drifts, or when export-bind cert_hash does not match transfer-cert cert_hash.
