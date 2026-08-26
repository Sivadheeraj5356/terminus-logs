# Relay coordinator contract

The edge relay coordinator under `/app/environment` pools TCP connections to shard endpoints declared in `/app/config/relay_policy.toml`. Workloads under `/app/fixtures/workloads/` describe ping rounds per shard.

Phases:

- `populate` executes checkout/ping/checkin rounds and marks governance ready.
- `idle` sleeps through the idle-close window then runs linger reconciliation on pooled sockets.
- `verify` exports artifacts only (usually combined via `--phase all`).

Cold `idle` before a successful `populate` on the same state database must exit `9`.

Static descriptor totals above `descriptor_ceiling` must exit `5`. Cross-surface export mismatches exit `6`. If the verify phase runs against an unpopulated or empty state database, it must exit `6`. Breaching the generation-adjusted effective limit `descriptor_ceiling - (pool_generation * 2)` must exit `7` without panicking.

The SQLite `generation_seals` table MUST contain a boolean (or integer) column named `sealed` alongside the `pool_generation` column.

`pool_peak` in the run report must stay at or below `descriptor_ceiling` for bundled sixteen-round workloads.

Every exported `pool_generation` in the run report, journal, and trace must be the post-increment ledger value returned after `mark_populated()` for the populate pass that produced the run. `mark_populated` must be called after all transports for the current run are opened. Idle sockets checked in during populate carry that generation tag.

Generational linger pinning: during idle reconciliation the governor must not reap every idle socket for an active unsealed generation. At least one idle socket per such generation stays pinned even when EOF. The pinned socket MUST remain in the pool for the duration of the current idle phase invocation; it may only be reaped on a subsequent call, even after the generation has been sealed within the same call. You cannot seal-then-immediately-reap within a single pass. Only after a generation is sealed in the SQLite ledger may its last pinned idle socket be reaped on a later idle invocation. The idle phase seals the populate generation when linger reconciliation completes.

Concurrent linger: idle socket sweeping must execute concurrently across the pool. Reclaim persistence and trace export require deterministic ordering — reclaim trace events by ascending `socket_id`, journal rows by ascending `round_index` then ascending `socket_id`.

Bundled smoke workload `smoke_4` has `workload_id` `smoke_4`, `round_count` 4, and `checkouts_total` 4. Bundled `smoke_16` has `checkouts_total` 16.
