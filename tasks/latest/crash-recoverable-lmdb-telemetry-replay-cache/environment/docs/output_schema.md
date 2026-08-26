# Report and matrix JSON fields

Each `telreplay` run emits `/app/output/.single_report.json` containing one per-scenario object. The matrix driver reads those objects, adds `body_sha256`, and assembles the envelope at `/app/output/matrix_report.json` plus `/app/output/report_seal.bin`.

Per-scenario objects under `matrix_report.json` → `scenarios` include timing, descriptor audit, correlation counts, and a self-hash field (`body_sha256`). The matrix envelope adds `matrix_digest` over scenario hashes in pack order.

## Per-scenario report object

| Field | Type | Semantics |
|-------|------|-----------|
| `schema_version` | int | report schema version (`1` for this generation) |
| `scenario_id` | string | pack id |
| `loops_run` | int | `--loops` value used |
| `initial_open_fds` | int | open FD count before replay |
| `final_open_fds` | int | open FD count after replay |
| `fd_delta` | int | `final_open_fds - initial_open_fds` |
| `leak_reproduced` | bool | `true` iff `fd_delta > 0`; otherwise `false` |
| `root_cause` | string | `sample_scan`, `error_correlate`, or `restart_walk` when a replay phase still leaks; otherwise `none` |
| `affected_pids` | int[] | sorted ascending, from correlation rule |
| `cache_hit` | bool | `true` only when the current report was reconstructed from the latest valid journal record whose input fingerprint matches; `false` for live replay, including `--no-resume` |
| `generation` | int | per-scenario journal generation represented by this report; starts at `1`, is retained on a cache hit, and increments only when a new record is appended |
| `input_fingerprint` | string | 64-character lowercase SHA-256 digest computed exactly as specified in `replay_journal.md` |
| `journal_bytes` | int | byte length of the scenario journal after startup recovery and any append performed by this invocation; greater than zero once a valid record exists |
| `recovered_records` | int | number of valid records retained when an invalid journal tail was truncated during this invocation; otherwise `0` |
| `samples_scanned` | int | cardinality of `samples` |
| `errors_seen` | int | cardinality of `errors` |
| `restarts_seen` | int | cardinality of `restarts` |
| `correlated_triples` | int | triples matching the window rule |
| `body_sha256` | string | lowercase hex digest (64 characters) of the canonical JSON object excluding itself (keys sorted, compact separators) |

## Matrix envelope

| Field | Type | Semantics |
|-------|------|-----------|
| `schema_version` | int | `1` |
| `scenarios` | object | one report object per pack entry, keyed by scenario id (`lane_alpha`, `lane_beta`, `lane_gamma`, `lane_delta`, `lane_epsilon`) |
| `matrix_digest` | string | lowercase hex digest (64 characters) over the UTF-8 concatenation of each scenario's `body_sha256` in pack order (no separators) |
