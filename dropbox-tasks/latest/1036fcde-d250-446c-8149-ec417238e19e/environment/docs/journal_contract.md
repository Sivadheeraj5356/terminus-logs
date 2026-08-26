# Journal export contract

Public contract for the supervised journal-wrapped oneshot `/app/bin/verify-journal-runs` and unit `verify-journal-export.service`.
The host-side batch must remain consistent when stdout is journal-wrapped with collector recycle
mid-burst, and when the same fixtures run under file-backed stdout. Host sources under `/app/environment`
must satisfy this document; the verifier rebuilds the oneshot driver from that tree before checking
outputs.

## Build and run

```bash
make -C /app/environment install
```

```bash
/app/bin/verify-journal-runs \
  --fixtures-dir /app/environment/pack \
  --out /app/output/run_records.json \
  --trace-out /app/output/export_trace.jsonl \
  --journal-out /app/output/span_journal.jsonl \
  --manifest-out /app/output/completion_manifest.jsonl \
  --audit-out /app/output/run_audit.jsonl \
  --ledger-state /app/output/run_ledger.state
```

Platform verification reruns this command; pytest flags such as `--ctrf` are harness-only. Independent digest checks may recompute sha256 material with `openssl dgst -sha256`.

## Fixture packs

Each JSON pack includes `sink_mode` (`wrap` for journal-wrapped stdout or `redirect` for file-backed stdout), `pipe_cap`, and `events` with `kind` in `seed`, `recycle`, or `wave`. Epochs default to `0000` until a `seed` event sets `writer_epoch` and `reader_epoch` (lowercase hex). Bundled stems include `pack_m1` through `pack_m6` and `pack_m8`. There is no bundled `pack_m7`; the verifier may add a runtime `pack_m7.json` to exercise discovery. Non-matching JSON such as `scratch_fixture.json` is ignored. Every `pack_m*.json` present under the fixtures directory before a run appears in all outputs on the same terms.

`pack_m3` exercises resume sidecar gating. `pack_m5` exercises multi-recycle large waves and overlay chunk planning.

## Slice policy config

`/app/environment/config/base.toml` and `/app/environment/config/overlay.toml` each define `[slice] chunk_divisor` (positive integer). Load base, then overlay; overlay wins on conflict.

Effective segment size for journal-wrapped wave planning is `max(pipe_cap / chunk_divisor, 512)`. Split each `wave` into segments of at most that size and emit one `wave_chunk` trace/journal row per segment. File-backed fixtures commit each segment immediately with `pending=0`.

## Journal-wrapped byte ledger

On journal-wrapped fixtures, staged bytes live in `pending` until flushed into `observed`:

- At each `recycle_before` row, move all pending bytes into observed, then set pending to zero.
- The matching `recycle_after` row keeps the same observed total with pending zero.
- After each recycle, the **next** journal-wrapped segment only (the first segment of the following wave) is a **probe close**: accept `min(planned_slice_size, max(pipe_cap / 2, 1))` bytes into `pending` and do **not** add them to `observed` on that `wave_chunk` row. Later segments in the same wave use normal rules.
- A non-probe journal-wrapped segment with `planned_slice_size > pipe_cap` accepts exactly `pipe_cap` bytes into `pending` and closes; smaller non-probe segments add their accepted bytes directly to `observed` with `pending = 0` on that row.
- When a segment closes into `pending`, assign `pending` to the accepted byte count for that segment (do not accumulate on top of prior pending).
- **Probe discard within a wave:** if a later slice in the **same** wave takes the non-close path (`observed += accepted` with `pending = 0`), any probe bytes still in `pending` from an earlier slice of that wave are **discarded** — they are not added to `observed` and are not carried to `wave_end`. Only probe bytes still pending after the final slice of a wave are flushed into `observed` at `wave_end`.
- Each wave iteration plans `planned_slice_size = min(wave_bytes_remaining, segment_size)` from the wave event, emits one `wave_chunk` row, then subtracts `planned_slice_size` from `wave_bytes_remaining` before the next iteration — even when the segment closed into `pending` instead of `observed`.
- Each completed wave ends with `wave_end` where any bytes still in `pending` are added to `observed`, then `pending` is set to zero before the row is emitted.
- Fixture `byte_span.observed_bytes` and every `wave_end` row follow the ledger above; it is **not** the sum of raw `wave` event `bytes` fields.

### Worked ledger: `pack_m5` (overlay `chunk_divisor = 2`, `pipe_cap = 8192`)

With `segment_size = max(8192 / 2, 512) = 4096`, the journal-wrapped ledger emits these `wave_chunk` / `wave_end` checkpoints (`observed`, `pending`):

| Step | Phase | observed | pending | Notes |
|------|-------|----------|---------|-------|
| 1 | wave_chunk | 4096 | 0 | first wave 9000 B, slice 4096 |
| 2 | wave_chunk | 8192 | 0 | slice 4096 |
| 3 | wave_chunk | 9000 | 0 | final slice 808 |
| 4 | wave_end | 9000 | 0 | |
| 5 | recycle_before / recycle_after | 9000 | 0 | |
| 6 | wave_chunk | 9000 | 4096 | probe close after recycle; 4096 B staged only |
| 7 | wave_chunk | 9904 | 0 | slice 904 added to observed; **4096 probe bytes discarded** |
| 8 | wave_end | 9904 | 0 | no pending left |
| 9 | recycle_before / recycle_after | 9904 | 0 | |
| 10 | wave_chunk | 9904 | 2000 | probe close; 2000 B staged only |
| 11 | wave_end | 11904 | 0 | flush remaining 2000 probe bytes → observed |

Final `observed_bytes` for `pack_m5` is **11904**, not 16000 (`9000 + 5000 + 2000`). Each `wave_chunk` row in `export_trace.jsonl` and `span_journal.jsonl` must match this ledger exactly for bundled overlay settings.

## Resume offset store

`/app/state/resume.offset` may contain JSON `{fixture_label, reader_epoch, observed_bytes}`. At fixture seed, add `observed_bytes` to the byte ledger only when both `fixture_label` and `reader_epoch` match the active seed. The image seeds a stale example; that preload must not change totals when epochs mismatch.

## Segment cache

`/app/state/segment.cache.json` maps cache keys to `{observed_bytes, reader_epoch}`. Keys are `fixture_label|reader_epoch`. Ignore cache rows from other epochs before processing waves for a fixture.

## run_records.json

Top-level JSON with a `runs` array (per-fixture report rows). Each row has `fixture_label`, `writer_epoch`, `reader_epoch`, `byte_span` (`start_offset`, `end_offset`, `observed_bytes`), `fingerprint` (32 hex chars), and `checkpoint_seal` (32 hex chars).

Digest fields are the first 32 hex characters of sha256 over the pipe-delimited payload:

- `fingerprint` = sha256(`writer_epoch|reader_epoch|start_offset|end_offset|observed_bytes`)
- `checkpoint_seal` = sha256(`journal_tail|fixture_label|observed_bytes`), where `journal_tail` is the last journal `link` for that fixture

## export_trace.jsonl

JSON Lines with `fixture_label`, `phase`, `observed`, `pending`, `writer_epoch`, `reader_epoch`, and `span_mix`. Phases include `seed`, `wave_chunk`, `wave_end`, `recycle_before`, and `recycle_after`.

`export_trace.jsonl` and `span_journal.jsonl` emit the same phases in the same global run order. Every trace row (including each `wave_chunk`) has exactly one matching journal row at the same position.

## span_journal.jsonl

Checkpoint phases in run order with `seq`, `fixture_label`, `phase`, `observed`, `pending`, and `link`. Journal `seq` is 1-indexed and contiguous across the full run (`1..N` with no gaps).

- `link` = sha256(`prev_link|seq|fixture_label|phase|observed|pending`), chaining from `prev_link=genesis`

## completion_manifest.jsonl

One line per fixture with `fixture_label`, `journal_tail`, `trace_lines`, `wave_chunks`, and `completion_seal`.

- `completion_seal` = sha256(`journal_tail|trace_lines|wave_chunks|observed_bytes`)

## run_audit.jsonl

After primary outputs are written, the binary performs a delayed audit pass rereading report, journal, and manifest from disk. One line per fixture with `fixture_label`, `journal_tail`, `completion_seal`, `checkpoint_seal`, and `audit_seal`.

- `audit_seal` = sha256(`journal_tail|completion_seal|checkpoint_seal|trace_lines`)

## run_ledger.state

Persists across verifier invocations as JSON with `run_count`, `prev_audit_tail`, and `chain_seal`. Each successful verify increments `run_count` (second run: `run_count` equals prior `run_count + 1`), sets `prev_audit_tail` to that run's final `audit_seal` (the last line in `run_audit.jsonl`), and sets `chain_seal` to sha256 over `prior_run_final_audit_seal|current_run_final_audit_seal|run_count|fixture_count`, where `prior_run_final_audit_seal` is the previous ledger file's `prev_audit_tail` (`genesis` on the first run) and `fixture_count` is the number of processed `pack_m*.json` fixtures in the current run.

Two consecutive verify runs with the same fixtures must produce identical journal link sequences and identical audit seal sequences.
