# Run report schema

`/output/relay_run_report.json` fields:

- `schema_version` (u32)
- `workload_id` (string)
- `round_count` (u32)
- `pool_generation` (u32) — post-increment ledger value after `mark_populated()` for the populate pass
- `checkouts_total` (u32)
- `reclaims_total` (u32)
- `journal_digest` (hex sha256)
- `pool_peak` (u32)
- `state_bytes` (u64)
