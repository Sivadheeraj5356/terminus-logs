Process JSONL holdback-buffer custody event shards from a task directory into structured JSON and CSV reports. Given a task root, load buffer configuration, discover lowercase `.jsonl` shards, replay buffer operations (`INGEST`, `HOLDBACK`, `DISPATCH`, `COMMIT`, `RELEASE`, `TRANSFER`, `PAUSE`, `UNPAUSE`) in contract order, and emit outputs under `/app/output/`. Normative discovery, reject precedence, duplicate suppression, per-lane ledger semantics, paused scope, executable path, source modules under `/app/replay_tool_src/src/` (`amount.rs`, `apply.rs`, `main.rs`, `output.rs`, `parse.rs`, `precedence.rs`, `reject.rs`, `replay.rs`, `types.rs`), and output formatting are in `/app/task_file/schema.md` and `/app/docs/holdback_buffer_replay_contract.md`. Do not edit contract files or mutate input task trees. Keep those modules separate; do not collapse them into one file.

## CLI

Run the installed holdback processor with exactly one `<task_root>` directory argument (for example `/app/task_file` or a copy under `/tmp/`). Wrong arity or a non-directory root is fatal before `/app/output/` is touched: silent nonzero exit, empty stdout and stderr, preserve existing `/app/output/` bytes. Success deletes and recreates `/app/output/` quietly, exits zero with empty stdout and stderr, and leaves the task tree unchanged. Load and validate config and events before deleting `/app/output/` on success.

## Event fields

Each event object has `event_id`, `timestamp`, `op`, `buffer_id`, `lane_id`, `qty`, and optional `peer_buffer_id`. On non-`TRANSFER` operations, `peer_buffer_id` may be omitted or the empty string `""`; both mean unset and must not reject. Only a **non-empty** `peer_buffer_id` on an op other than `TRANSFER` rejects `BAD_CONTROL`. `TRANSFER` requires a non-empty `peer_buffer_id` naming an existing buffer.

## Processing summary

Each buffer tracks per-`lane_id` filled and holdback slices; buffer totals are the sums of those slices. `HOLDBACK` moves qty from the event lane's filled slice to that lane's holdback (all-or-nothing). `DISPATCH` spends holdback before filled: debit holdback lanes in ascending `lane_id` order, then filled lanes in ascending `lane_id` order. `COMMIT` and `RELEASE` use the requesting lane's slice with partial `applied_qty` caps. `TRANSFER` moves source-lane holdback to the peer buffer's same `lane_id` holdback slice. `BUFFER_PAUSED` blocks `INGEST` and `DISPATCH` only; `HOLDBACK`, `COMMIT`, `RELEASE`, and `UNPAUSE` still apply on `HOLD` buffers. Replay tie-break is ascending `(timestamp, events-relative path, 1-based line number)`. Duplicate successful `event_id` lines increment summary only (no reject row); rejected ids do not enter the seen set; matching is case-sensitive exact equality.

## Outputs

On success write `/app/output/result.json`, `/app/output/audit.csv`, and `/app/output/rejects.csv`. `result.json` must match Python `json.dumps(..., indent=2, sort_keys=True)` on the same data plus exactly one trailing `\n` newline at every nesting depth. CSV headers, buffer/summary fields, and reject reason tokens: `/app/task_file/schema.md`.
