# k9 fleet desk-trace contract

Operational seal for the systemd host fleet rollout documented in
/app/docs/system-administration-workflow.md. Plain-language terms (desk, k9,
socket-activation, xr4 depth, WAL barrier) are defined there.

## Output path


`/app/output/k9_trace.json`

## Row shape

Each record in `rows` contains:

- `scenario` (int) — desk-run index 0 through 3. Directory names `s0`…`s3` under
  `/app/cases/seq` are fixture paths only; never emit the string `s0` as the
  scenario value.
- `phase` (`sk8`, `fp3`, `sr5`, or `xr4`)
- `target` (string)
- `marker` (string)
- `sequence` (int)
- `epoch` (int) — action code on emitted rows. sk8, fp3, and sr5 rows use `0`.
  Reservation `epoch` in `p0.res` influences xr4 depth selection only; never copy
  reservation epoch into sk8/fp3/sr5 rows.

Root field `chain_fingerprint` is a sha256 hex string.

## Sequence binding

Per scenario index, read ledger integers from that scenario's on-disk `b0.evt`
snapshot at invoke time. Sequence ordinals are ledger-grounded:

- fp3 `release` binds to a ledger field — not xfer `issue`, not conditional on
  `stage` when ledger anchor differs.
- sk8 `clean` and sr5 `done` bind to ledger `settle` with distinct phase offsets.
- Re-invoking with the same xfer `sig` must reuse the sk8-slot clean ordinal for
  that scenario index and source key, not re-derive from xfer `issue`.

When ledger snapshot bytes change on disk between invokes for the same index,
re-read `b0.evt` before deriving sequences. Cached ledger values from an earlier
read must not survive a snapshot replacement.

## Fixture layout

Each scenario under `/app/cases/seq/sN/` ships three key-value snapshots:

- `a0.evt` — xfer fields including `issue`, `sig`, `source`, and `target`
- `b0.evt` — ledger integers `stage`, `anchor`, and `settle`
- `p0.res` — reservation fields including `tail`, `epoch`, `rank_a`, and `rank_b`

## xr4 depth listing

xr4 rows use `sample_<sector>` markers. Emit one xr4 row per listed sector.
Target strings for xr4 come from the xfer snapshot (`a0.evt` `target` field);
sk8/fp3/sr5 use `source`.

Depth listing is reservation-driven from `p0.res` (`tail`, `epoch`, `rank_a`,
`rank_b`) and the scenario index. Ledger overlays that replace only `b0.evt`
change sequence ordinals; they do not add or remove xr4 sectors.

### Sector selection rules

- Index 0: head only — sector `0`.
- Index 1: head `0`, mid `64`, plus `rank_b` when `rank_b > epoch` (not `rank_a`).
- Index 2: head `0`, mid `64`, plus `rank_a`.
- Index 3: head `0` and tail floor `max(tail, 512)` only — no mid `64`.

Shallow listings that stop at the head group alone are incorrect when mid or
rank/tail sectors are required for that index.

### Per-scenario table (shipped public fixtures under `/app/cases/seq`)

| Index | `p0.res` (tail, epoch, rank_a, rank_b) | Required `sample_*` sectors |
|-------|----------------------------------------|-----------------------------|
| 0 | 512, 2, 1, 2 | `0` |
| 1 | 512, 3, 2, 4 | `0`, `64`, `4` (`rank_b` because 4 > 3) |
| 2 | 512, 4, 3, 6 | `0`, `64`, `3` (`rank_a`) |
| 3 | 4096, 5, 4, 8 | `0`, `4096` (tail floor; **no** `64`) |

Index 3 never emits `sample_64`. Hidden ledger overlays on `b0.evt` keep the same
sector list for each index; only `sequence` values tied to ledger `settle` move.

## Markers

Per scenario the trace carries one `sr5` marker (`done`), one `sk8` marker
(`clean`), one `fp3` marker (`release`), and one or more `xr4` sample markers.

## chain_fingerprint

Compute `chain_fingerprint` as the sha256 hex digest of UTF-8 text formed by:

```
scenario,phase,target,marker,sequence
```

One line per row, sorted lexicographically, newline-terminated. The `epoch` field
is excluded from the fingerprint payload.

## Barrier sequence invariants

- For scenario index 1 or later, fp3 `release` sequence is strictly less than sk8
  `clean` and sr5 `done` for the same target unless reservation `epoch` is 9.
- Scenario index 0 rows match the frozen baseline shipped in desk-run cases.
- Emitted report rows appear in contract phase order within each scenario index
  (sk8, fp3, sr5, xr4).

## WAL line format

Append log path: `/app/desk-state/wal/chain.wal`

Each WAL line is a JSON record, a tab, then the decimal CRC32 of the payload
`scenario:step:seq` (UTF-8, same polynomial as Python `zlib.crc32`).

## Step order

For scenario index 0 any step order is accepted. For index 1 and later, the folded
append log records fp3 steps before sr5 steps; duplicate step names within one
scenario are skipped. The log must record `release` before `clean` before `done`.
The checkpoint seal must be written only after the append-log steps for that invoke
are appended. `k9_emit` refuses when append-log order, CRC lines, or checkpoint seal disagree.

## Desk-run repeat-stability

`k9_invoke --scenario N` writes `/app/desk-state/epoch_N.json`. Re-invoking
the same scenario index must replace (not accumulate) epoch-cache rows for that
index. sk8 persists a slot under `/app/desk-state/signal/` on first invoke keyed
by scenario index and xfer `source` (`s<N>-<source>.slot`). sr5 persists a mount
slot (`*.mount`) for stale-signature detection on first invoke.

## Emit prerequisites

`k9_emit` requires epoch caches for indices 0 through 3, a valid checkpoint whose
`order_seal` matches the append log, intact WAL CRC lines, and contract phase order
in emitted rows spanning all four phases.

## Checkpoint

`checkpoint.json` stores `last_scenario`, `wal_seq`, `order_seal`, and `valid`.
After each successful scenario invoke, checkpoint `wal_seq` equals the append-log
tail: `wal_seq == chain[-1]["seq"]` (the `seq` field of the final WAL record).
After deliberate checkpoint drift, `k9_recover` rebuilds the checkpoint from the
WAL and restores `wal_seq` to `_wal_records[-1]["seq"]`. A healthy checkpoint
after invoke or successful recover has `valid` true. `k9_recover` must return a
non-zero exit status when CRC lines are tampered, step order is invalid, or phase
validation fails — not only mark the checkpoint invalid internally.

## Harness verification

Independent digest helpers recompute `chain_fingerprint` via `/app/docs/digest_ref.sh`
and WAL CRC payloads from fixture bytes.


## Hidden ledger overlays

The verifier may replace on-disk ledger snapshots under `/app/cases/seq` using alternate
bytes rooted at `TB3_FIXTURE_ROOT` when that environment variable is set. When unset, the
default hidden overlay root is `/tests/hidden/seq`. Overlay replacement changes ledger
`b0.evt` only; reservation `p0.res` and xr4 sector lists stay as in the per-scenario table.
