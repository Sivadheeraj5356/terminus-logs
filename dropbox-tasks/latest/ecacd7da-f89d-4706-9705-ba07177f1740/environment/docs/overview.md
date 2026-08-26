# Compactor ram seat driver

The compactor ram seat driver replays operator journal events against on-disk CMPR ram blocks to rebuild the live seating ledger and produce operator-facing artifacts.

## Purpose

Yard operators publish schedules as JSONL journals. Each line is one durable event with a monotonic sequence number, an operation name, a scenario tag, and optional fields such as `cycle_epoch`, `ram_block_id`, or `event_id`. The driver reads CMPR blocks from `/app/data/rams/`, updates in-memory ledger state, and may emit a seat log and operator report.

## CLI modes

| Mode | Usage |
|------|--------|
| Normal seat | `compactor_seat --seat <journal> --emit-log <path> [--emit-report <path>]` |
| Recovery seat | `compactor_seat --seat-recover <journal> --emit-log <path> [--emit-report <path>]` |
| Catalog probe | `compactor_seat --probe-shift-table` (JSON on stdout) |

Recovery seat loads `/app/snapshot/compactor_anchor.json` as the starting ledger. Normal seat starts from an empty ledger.

## Emitted artifacts

### Seat log (`seat_log.jsonl`)

JSONL rows with at least `kind`, `scenario_tag`, and `seq`. Rows with `kind` of `ram_seated` also carry `ram_id`.

Normal seat runs preserve an existing log byte-for-byte, append new rows, and continue emitted `seq` values from the greatest existing value plus one; a new log starts at 1. Recovery preserves the complete pre-invocation prefix and appends any rows produced by the recovery attempt. Rows already present before the process starts, including from prior runs, must never be removed or rewritten.

### Operator report (`seat_report.json`)

Single JSON object:

| Field | Type | Meaning |
|-------|------|---------|
| `rams_seated` | integer | Count of rams in the live ledger after replay |
| `guides_marked` | integer | Number of guide-mark events applied |
| `tonnage_recorded` | integer | Mathematical sum of `tonnage_kg` across seated rams (raw kilograms, no scaling; may exceed 32-bit range) |
| `state_digest` | string | Lowercase 64-character SHA-256 digest of the canonical live-ledger encoding described below |
| `rollback_performed` | boolean | Whether recovery rolled back to the anchor |
| `ready` | boolean | Whether the run completed without rollback and has seated rams |

## Durable journal ordering and identity

Journal files may list events out of sequence-number order. Replay must apply events in ascending durable `seq` order, not raw file line order.

Two records with the same `seq` and identical parsed payload (`op`, `scenario_tag`, `cycle_epoch`, `ram_block_id`, and `event_id`) are exact duplicates. They apply once and produce no duplicate mutation or log row.

Two records with the same `seq` but different parsed payloads are a conflict. The command must exit nonzero before applying any journal mutation or publishing any new output.

A non-empty `event_id` identifies one durable event. Only the first retained row in durable order may apply; later rows with the same `event_id` are ignored even when they carry a different `seq` or `op`.

## Replay expectations

Each `scenario_tag` is independent for guide semantics. Within a tag, every `guide_marked` log row must appear before any `guide_cleared` row for that same tag when both are present.

### Ram seating

- `ram_seat` reads the referenced CMPR block. The block body encodes `ram_id|tonnage_kg`; the trailing checksum must validate. CMPR layout and runtime paths are summarized in `/app/docs/runtime_notes.txt`.
- Publishing the same ram with the same block checksum again is a no-op when the effective seating epoch is the same or older than the ram's stored cycle ownership.
- Publishing the same `ram_id` with the same checksum at a newer effective epoch refreshes that ram's stored cycle ownership without increasing seated count, without emitting another `ram_seated` row, and while advancing durable ledger revision so dependent views observe the change.
- Publishing the same `ram_id` with a different checksum is a revision: update checksum, tonnage, effective epoch, and emit one new `ram_seated` row.
- The effective epoch for a `ram_seat` is the event's explicit nonzero `cycle_epoch` when present; otherwise it is the active cycle epoch at apply time.

### Cycle epochs and guide clear

`cycle_arm` sets the active cycle epoch to the row's `cycle_epoch` value exactly and advances journal revision once; epochs need not be contiguous. `guide_clear` releases rams seated under earlier cycle epochs from the live ledger while keeping rams seated at the current epoch or later, and advances journal revision once.

#### `journal_revision` increments

`journal_revision` is a monotonic unsigned 64-bit live-ledger counter. It is hashed into `state_digest` as uint64 little-endian (after all live ram records and the ledger `cycle_epoch`) and echoed in `--probe-shift-table` snapshots. The verifier replays journals with these exact bump rules.

**Increments by exactly one** when replay applies:

1. **`cycle_arm`** — sets the ledger's active `cycle_epoch` to the event's `cycle_epoch` field (epochs need not be contiguous).
2. **`ram_seat`** that seats a **new** `ram_id`, or seats an existing `ram_id` with a **different CMPR checksum** (checksum revision; emits one `ram_seated` row).
3. **`ram_seat`** that re-publishes an existing `ram_id` with the **same CMPR checksum** at a **strictly newer effective `cycle_epoch`** (silent cycle-ownership refresh: no new `ram_seated` row and no `rams_seated` count change, but revision still advances).
4. **`guide_clear`** — removes from the live ledger every ram whose seated `cycle_epoch` is strictly less than the active ledger `cycle_epoch`.

**Does not change** when replay applies:

- **`ram_seat`** that re-publishes the same `ram_id` and checksum at the **same or older** effective `cycle_epoch` (no-op repeat seat).
- **`guide_mark`** — log-only; affects `guides_marked` but not live ram semantics or revision.

Effective `cycle_epoch` for `ram_seat` is the event's explicit nonzero `cycle_epoch` when present; otherwise it is the active ledger `cycle_epoch` at apply time.

| Operation | Increments `journal_revision`? |
|-----------|-------------------------------|
| `cycle_arm` | Yes — sets active `cycle_epoch` |
| `ram_seat` (new ram or checksum revision) | Yes |
| `ram_seat` (same checksum, newer effective epoch) | Yes — silent cycle refresh without another `ram_seated` row |
| `ram_seat` (same checksum, same or older epoch) | No |
| `guide_clear` | Yes — releases prior-cycle rams |
| `guide_mark` | No — log-only |

### Catalog probe

`--probe-shift-table` prints JSON with `first`, `second`, `truth`, `isolated`, and `isolated_truth` objects. Each snapshot includes `cycle_epoch`, `journal_revision`, `ram_count`, and a `rams` map.

The probe exercises the shift-table cache in two ways:

1. After a revision-only ledger change (journal revision advances without a cycle epoch change), the second cached view must match live truth while the first view remains stale on ram count.
2. Two independent ledgers may share identical `cycle_epoch` and `journal_revision` values while containing different ram records, or share a compact fingerprint while differing semantically. Materializing a cached view for each ledger must return that ledger's ram map and counts, not a view built for another ledger.

The probe JSON also includes `collision_a`, `collision_b`, `collision_truth_a`, and `collision_truth_b` for equal-epoch, equal-revision fingerprint collision exercises.

### Live ledger authority and `state_digest`

The live ledger (ram map, cycle epoch, journal revision) is authoritative for operator totals. Shift-table cache and lane rollup views are transient accelerations; they must not be the source of report counts when they lag behind the ledger.

For `state_digest`, order live ram records by ascending `ram_id`. Feed the sha256 digest with each raw UTF-8 `ram_id` (no delimiter), then its checksum, tonnage, and ram cycle epoch as unsigned 32-bit little-endian integers. After all live rams, feed the ledger cycle epoch as unsigned 32-bit little-endian and journal revision as unsigned 64-bit little-endian. Historical, cleared, and log-only rows are excluded; an empty ram map still contributes the ledger epoch and revision.

## Normal publication contract

For normal `--seat` runs, requested log and report artifacts are one publication unit. Replay, report construction, staging, and final publication must all succeed together. If journal parsing, durable-sequence conflict detection, CMPR reading, checksum validation, replay, report construction, staging, or final publication fails, the process exits with a nonzero status. Existing final log and report files must remain byte-identical. A final path that did not exist before the failed run must remain absent. Temporary staging files must be cleaned up.

## Recovery contract

Recovery preserves the pre-invocation seat-log prefix byte-for-byte, inspects all valid pre-existing log rows, and begins newly emitted rows at one greater than the highest existing integer `seq`, or at 1 when no prior row exists. Do not derive the next value from row count or the last physical line.

Only CMPR block read or checksum failures during `ram_seat` may convert replay failure into successful anchor rollback. Journal file read failure, malformed JSON, durable-sequence conflict, unknown operation, anchor snapshot read or parse failure, report construction or serialization failure, log or report staging failure, final publication or rename failure, and invalid output paths must exit nonzero without publishing a rollback report, preserve existing final log and report bytes, leave absent final paths absent, and remove temporary staging files.

On eligible CMPR failure during recovery replay:

1. Restore the live ledger to the anchor snapshot (rams, cycle epoch, and journal revision from `/app/snapshot/compactor_anchor.json`).
2. Discard partial ledger effects from the failing and subsequent events.
3. Preserve every seat-log row that existed before this process started, plus any rows emitted before the failure during the current attempt.
4. Publish both `--emit-log` and `--emit-report` paths together with anchor ledger totals and digest.
5. Set `rollback_performed` true and `ready` false in the report.

Rollback does not remove prior log rows; all surviving rows remain strictly increasing and unique. Recovery publication failure is not a successful rollback result.

## Determinism

Replaying the same journal from the same starting output state must produce byte-identical operator reports. Repeated publications within one journal must not inflate seated counts or duplicate applied `ram_seated` rows beyond what revision semantics allow.
