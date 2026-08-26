# Run contract

Build after source edits:

`/usr/local/cargo/bin/cargo build --release --offline --manifest-path /app/environment/Cargo.toml` with `CARGO_TARGET_DIR=/app/environment/target`.

Binary: `/app/environment/target/release/trainctl`.

## Commands

`train` and `continue` accept:

- `--plan` — plan TOML under `/app/environment/plans/`
- `--mode` — `serial` or `parallel`
- `--seed` — unsigned seed (verifier uses `17`)
- `--accum-steps` — window size (verifier uses `4`)
- `--out` — output root (verifier uses `/app/output`)
- `--from` — vault directory for `continue` (verifier uses `/app/output/vault`; any valid snapshot directory works, including a relocated copy such as `/app/output/vault_relocated`)

Plans under `/app/environment/plans/`:

- `/app/environment/plans/tiny.toml` — uninterrupted full runs
- `/app/environment/plans/mid_halt.toml` — train snapshot after step 1 completes
- `/app/environment/plans/mid_halt_split.toml` — train snapshot at step 1, continue snapshot at step 2
- `/app/environment/plans/mid_window.toml` — train snapshot after two admits of the current accum window (`snapshot_after_admits = 2`, partial window)
- `/app/environment/plans/nested_window.toml` — train snapshot after three admits of the current accum window (`snapshot_after_admits = 3`, three-quarter partial window)
- `/app/environment/plans/triple_halt.toml` — train snapshot at step 2, continue snapshot at step 3

## Artifacts

`/app/output/run_trace.jsonl` — JSONL with `seq`, `slot`, `phase`, `tag`, `payload_fp`, `step_index`.

`/app/output/pass_transcripts/pass_<n>.json` — `step_digest`, `balance_tally`, `pending_slots`, `mode`, `acc_checksum`.

`/app/output/vault/manifest.json` — `last_tag`, `last_step`, `pending_count`, `wave_offset`.

`/app/output/vault/acc.bin` — little-endian `f32` accumulator bytes for the partial or completed window at snapshot time.

`/app/output/vault/tags.bin` — little-endian `u64` tag bytes for pending admits in the snapshot window.

`/app/output/wal.log` — seal records of the form `seal:<step>:<comma-separated-tags>` used when the tag sidecar is missing on continue.

## Fingerprints

All fingerprint and checksum fields use sha256; stored values are the first 16 lowercase hex characters unless noted otherwise.

Payload fingerprint: sha256 hex digest of little-endian `f32` bytes from the plan batch vector (first 16 hex chars stored in trace `payload_fp`).

Step fingerprint: first 16 hex chars of sha256 over UTF-8 `step:{step_index};tags:{sorted_tags_csv}`. Tags in the CSV must appear in sorted ascending numeric order. The pass `mode` field records the run profile but is not hashed.

Accumulator checksum: first 16 hex chars of sha256 over the little-endian `f32` bytes of the live accumulator vector at step completion; stored in pass `acc_checksum`.

End-of-run tally: JSONL admit events minus accum window times completed steps.

At snapshot boundaries, `pending_count` in the vault manifest must equal the number of eight-byte tag entries in `tags.bin` and must match `len(pending_slots)` in the pass transcript for the same halted step when that pass exists.

Continue must restore partial-window accumulator bytes and pending tags before admitting the remainder of the interrupted wave. When `wave_offset` is non-zero, the scheduler skips that many slots in the resumed wave.

Gauge stdout lines (`gauge l2=… within=…`) are diagnostic only.
