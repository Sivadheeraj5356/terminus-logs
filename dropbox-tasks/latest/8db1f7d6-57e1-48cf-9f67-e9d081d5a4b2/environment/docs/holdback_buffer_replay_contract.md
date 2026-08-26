# Holdback buffer replay contract

## Deliverables

The processor under `/app/replay_tool_src/` must yield a native Linux ELF at `/app/bin/replay_tool` using only files already present in the image. Grading rebuilds that binary from the edited crate sources before running pytest; replacing the binary without fixing the Rust modules will not survive verification. On success, delete and recreate `/app/output/` and write `result.json`, `audit.csv`, and `rejects.csv`. Do not modify the input task tree on success.

## CLI

Exactly one argument: the task root directory. Wrong arity is fatal: exit nonzero with empty stdout and stderr while preserving any existing `/app/output/` bytes.

## Fatal validation

Exit nonzero silently and preserve `/app/output/` when: wrong CLI arity; task root not a directory; invalid UTF-8; empty or duplicate `config/buffers.json`; unknown keys on buffer or event objects; missing or empty `events/`; no lowercase `.jsonl` files under `events/`; unparseable JSON on a non-blank shard line; empty `event_id` or `buffer_id`; unknown `op`. Whitespace-only lines and valid non-object JSON values are skipped, not fatal.

## Discovery and ordering

Discover `events/**/*.jsonl` recursively; only lowercase `.jsonl` extensions match. Normalize `\r\n` and bare `\r` before line counting. Skip whitespace-only lines and valid JSON that is not an object. Sort events by `(timestamp, relative path under events/, 1-based line number)`.

## Reject precedence

Evaluate field-format and control rules before buffer lookup when both could apply. `BAD_CONTROL` on non-`TRANSFER` ops only when `peer_buffer_id` is non-empty (empty string or omission means unset); `BAD_CONTROL` / `BAD_QTY` / `BAD_LANE` before `UNKNOWN_BUFFER`; duplicate suppression only after a successful apply reserves an `event_id`. Full op semantics, lane-slice rules, `DISPATCH` debit order, and reason tokens: `/app/task_file/schema.md`.

## Output shape

`result.json` uses Python `json.dumps(..., indent=2, sort_keys=True)` plus trailing newline. Buffers sorted ascending by `buffer_id`. CSV headers and per-op `applied_qty` magnitudes: `/app/task_file/schema.md`.
