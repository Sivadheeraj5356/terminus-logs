# Usage feed contract

## JSONL shards

Path: every `*.jsonl` file under `/app/data/usage/`.

Each non-empty line is one JSON object. Blank lines are ignored and do not increment the source line number.

### Required fields

| field | type | rule |
| --- | --- | --- |
| `eventId` | string | Non-empty unique identifier within the shard |
| `workAlias` | string | Non-empty; resolved via catalog aliases |
| `territory` | string | Must exist in `territory_calendar.json` |
| `medium` | string | One of `SVOD`, `AVOD`, `THEATRICAL` |
| `capturedAt` | string | UTC instant `YYYY-MM-DDTHH:MM:SSZ` |
| `playCount` | integer | `>= 0` |
| `rerunIndex` | integer | `>= 0` |
| `revision` | integer | `>= 1` |

### Malformed validation

Validate each parsed object in priority order. Malformed rows are skipped and emit one audit line to stderr only (not part of graded outputs).

Audit format, exactly:

`audit,<reason>,<eventId>,<manifestRel>,<sourceLine>`

- Use LF line endings.
- `manifestRel` is the normalized path relative to `/app`, for example `data/usage/d.jsonl`.
- `sourceLine` is the 1-based count of non-blank data lines in that shard.
- For `bad_json`, use `-` as `eventId` because no trusted object exists.
- Unknown JSON fields are ignored after validation succeeds.

| reason | condition |
| --- | --- |
| `bad_json` | Line is not valid JSON or is not an object |
| `bad_id` | `eventId` or `workAlias` is empty |
| `bad_territory` | Unknown territory code |
| `bad_medium` | Medium not in allowed set |
| `bad_time` | `capturedAt` is not valid UTC `YYYY-MM-DDTHH:MM:SSZ` |
| `bad_play_count` | `playCount` is negative or not an integer |
| `bad_rerun` | `rerunIndex` is negative or not an integer |
| `bad_revision` | `revision` is not an integer `>= 1` |

Example: if a shard contains one valid row, one blank line, then a row with `playCount:-1`, the bad row has `sourceLine` 2.

### Ingest metadata

Load shards in manifest order from `/app/config/usage_ingest_order.json` (`files` array). Files absent from the manifest are processed after all listed files, sorted lexicographically by basename.

Each loaded row records its 1-based source line number (first data line is line 1; blank lines do not increment the counter). The same source-line number is used by dedup tie-breaks and malformed-row audit lines.

### Dedup grouping

After alias resolution, deduplicate by `(workId, territory, dayLocal, medium, rerunIndex)`.

`dayLocal` is computed per `allocation_contract.md`.

Winner precedence (first difference wins):

1. Highest `revision`
2. Latest `capturedAt` (UTC epoch seconds)
3. Later position in the ingest manifest (higher index in `files`)
4. Later source line number

Losers are dropped silently (no audit artifact).

### Accrual per surviving row

`grossMicroCents = trunc(playCount * baseRateMicroCents * territoryMultiplier * rerunMultiplier / (10000 * 10000))`

- `baseRateMicroCents` and `rerunMultiplier` from `rate_tiers.toml` (see `rate_and_recoupment.md`)
- `territoryMultiplier` from `territory_calendar.json`
- Integer division truncates toward zero at each step; the final division is truncating integer division

Aggregate surviving rows into daily buckets `(workId, territory, dayLocal, medium)` by summing `playCount` and `grossMicroCents`.
