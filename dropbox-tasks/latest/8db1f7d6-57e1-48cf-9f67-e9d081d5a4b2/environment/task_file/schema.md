# Holdback buffer replay schema

Reference contract for the replay binary at `/app/bin/replay_tool`.

## Fatal exit conditions

Exit `1` with empty stdout and stderr and **preserve existing `/app/output/` bytes** on:

- Wrong CLI arity (zero arguments or two-or-more arguments).
- Task root is not a directory.
- Invalid UTF-8 in `config/buffers.json` or any event shard.
- Missing, empty, or duplicate `buffer_id` in `config/buffers.json`; invalid `status`; unknown keys on buffer config objects.
- Missing `events/` directory, or `events/` exists but **zero** discovered lowercase `.jsonl` shards (including task roots whose only shards use uppercase `.JSONL`).
- Unparseable JSON on a non-blank shard line (syntax error). Valid JSON that is not an object — arrays, strings, bare numbers — is **skipped**, not fatal.
- Unknown keys on event objects.
- Empty `event_id` or empty `buffer_id` on a parsed event object line.
- Unknown `op` string on a parsed event object line.

Load and validate config and events **before** deleting `/app/output/` on success.

## Config

**buffers.json** — non-empty JSON array. Each object has exactly `buffer_id` (string, unique), `capacity` (integer), and `status` (`OPEN` or `HOLD`). No other properties.

**Event JSONL** — discover lowercase `.jsonl` shards recursively. Normalize `\r\n` and bare `\r` before line split. Skip whitespace-only lines. Skip valid JSON values that are not objects (for example `[1,2,3]`, `"hello"`, `42`). Each replayed line is a JSON object with `event_id`, `timestamp`, `op`, `buffer_id`, `lane_id`, `qty`, and optional `peer_buffer_id`. On non-`TRANSFER` ops, `peer_buffer_id` may be omitted or `""` (both mean unset). `TRANSFER` requires a non-empty `peer_buffer_id`. Supported ops: `INGEST`, `HOLDBACK`, `DISPATCH`, `COMMIT`, `RELEASE`, `TRANSFER`, `PAUSE`, `UNPAUSE`.

## Output JSON

`result.json` top-level keys: `buffers`, `summary`. Each buffer: `available`, `buffer_id`, `capacity`, `dispatched`, `filled`, `holdback`, `status`. **`available` equals `capacity - filled - holdback`**. **`buffers` sorted ascending by `buffer_id`**. Summary: `applied_events`, `buffers_total`, `duplicate_events`, `rejected_events`, `total_dispatched`, `total_filled`, `total_holdback`. Must **byte-match** Python `json.dumps(..., indent=2, sort_keys=True)` plus a trailing newline — `serde_json::to_string_pretty` alone is insufficient; keys must be sorted at every nesting depth.

## CSV output

`audit.csv` header exactly: `event_id,timestamp,buffer_id,lane_id,applied_qty`

`rejects.csv` header exactly: `event_id,timestamp,buffer_id,reason`

Both CSV files list rows in replay order. `PAUSE` and `UNPAUSE` audit rows use `lane_id` `"-"` and `applied_qty` `0`.

## Replay ordering

Recursive `events/**/*.jsonl` (lowercase extension only). Normalize `\r\n` then bare `\r` before line counting. Sort by `timestamp`, relative POSIX path under `events/`, then 1-based physical line.

## Control ops

`PAUSE`/`UNPAUSE`: `lane_id` exactly `"-"`; `qty` exactly `0`, `+0`, or `-0`. Wrong lane or nonzero qty → `BAD_CONTROL` before `BAD_LANE`. Evaluate control-field `BAD_CONTROL` before `UNKNOWN_BUFFER` lookup — a `PAUSE` with real `lane_id` on an unknown `buffer_id` still rejects `BAD_CONTROL`, not `UNKNOWN_BUFFER`. Empty `lane_id` on control → `BAD_CONTROL`. Second `PAUSE` on `HOLD` or `UNPAUSE` on `OPEN` → `BAD_CONTROL`. Audit `applied_qty` is `0`.

## Paused scope

`BUFFER_PAUSED` blocks `INGEST` and `DISPATCH` only — `HOLDBACK`, `COMMIT`, `RELEASE`, and `UNPAUSE` still apply on `HOLD` buffers. `TRANSFER` blocked when either side is `HOLD`.

## Holdback ledger

Each buffer maintains per-`lane_id` filled and holdback slices. Buffer `filled` and `holdback` equal the sums of those slices. `INGEST` adds to the event lane's filled slice, rejecting `OVER_CAPACITY` when the buffer's `available` (`capacity - filled - holdback`) is less than `qty`.

`HOLDBACK` moves qty from the event lane's filled slice to that lane's holdback slice (all-or-nothing). `INSUFFICIENT_FILLED` when that lane's filled slice is too small, even if another lane still has filled units.

`DISPATCH` spends aggregate holdback before aggregate filled: debit holdback slices in ascending `lane_id` order, then filled slices in ascending `lane_id` order. `OVER_CAPACITY` when `holdback + filled < qty`.

`COMMIT` moves min(qty, lane holdback) from the event lane's holdback slice to that lane's filled slice. `INSUFFICIENT_HOLDBACK` when that lane's holdback slice is `0`, even if another lane still has holdback.

`RELEASE` moves min(qty, lane filled) out of the event lane's filled slice. `NOTHING_TO_RELEASE` when that lane's filled slice is `0`, even if another lane still has filled units.

## TRANSFER

Moves qty from the source lane's holdback slice to the same `lane_id` holdback slice on the destination via `peer_buffer_id`. Evaluate source-lane `INSUFFICIENT_HOLDBACK` before destination `OVER_CAPACITY` when both would apply. `INSUFFICIENT_HOLDBACK` when the source lane slice is too small, regardless of other lanes' holdback on the source buffer. `OVER_CAPACITY` when the destination buffer's `available` is less than `qty`. A **non-empty** `peer_buffer_id` on any op other than `TRANSFER` → `BAD_CONTROL` (empty string or omission means unset). Unknown peer → `UNKNOWN_BUFFER`.

## Event identity

Rejected `event_id` does not mark seen; only the first successful apply reserves an id. Duplicate detection runs before soft reject for ids already successfully applied. A later row with the same `event_id` increments `duplicate_events` only and must not change buffer balances, audit rows, or rejects. Never emit a `DUPLICATE_EVENT` reject row. Duplicate matching uses **case-sensitive** exact string equality — `evt` and `EVT` are distinct ids.

Only extension exactly `.jsonl` counts. If `events/` contains only uppercase extensions such as `.JSONL`, treat as zero selectable shards (fatal).

Replay tie-break is `(timestamp, events-relative path, 1-based line)` — never `event_id` alone. Normalize bare `\r` line endings before parsing.

Load config and events before deleting `/app/output/`; fatal exits preserve existing output bytes.

`DISPATCH` debits holdback lanes in ascending `lane_id` lex order, then filled lanes. `buffers` array sorted ascending by `buffer_id`; JSON uses `sort_keys=True` at every nesting level.

## Reject reasons

`BAD_QTY`, `BAD_CONTROL`, `BAD_LANE`, `UNKNOWN_BUFFER`, `BUFFER_PAUSED`, `OVER_CAPACITY`, `INSUFFICIENT_FILLED`, `INSUFFICIENT_HOLDBACK`, `NOTHING_TO_RELEASE`.

Mutating `qty` (except `PAUSE`/`UNPAUSE`): plain ASCII digits only, value in `1..9223372036854775807`, no `+`/`-` prefix, no leading zeros, no scientific notation.

Non-control ops: empty or `"-"` `lane_id` → `BAD_LANE`.

Control-field `BAD_CONTROL` is evaluated before `UNKNOWN_BUFFER` lookup — a `PAUSE` with real `lane_id` on an unknown `buffer_id` still rejects `BAD_CONTROL`, not `UNKNOWN_BUFFER`.
