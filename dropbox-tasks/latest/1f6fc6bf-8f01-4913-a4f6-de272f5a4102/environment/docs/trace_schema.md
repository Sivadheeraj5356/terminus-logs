# Trace schema

`/output/relay_trace.ndjson` records:

- `socket_id` (u32)
- `phase` (string: checkout, pong, checkin, reclaim)
- `pool_generation` (u32) — post-increment ledger value after `mark_populated()` for the populate pass
- `shard` (u32)

Reclaim-phase records must appear in ascending `socket_id` order within the NDJSON file.
