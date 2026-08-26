# Run contract

Build after source edits:

`/usr/local/cargo/bin/cargo build --release --locked --offline --manifest-path /app/environment/Cargo.toml` with `CARGO_TARGET_DIR=/app/environment/target`.

Binary: `/app/environment/target/release/diffkit`.

## Commands

`run` and `continue` accept `--plan`, `--mode` (`serial` or `parallel`), `--seed`, `--out`, and `continue` also accepts `--from`.

Plans: `/app/environment/plans/tiny.toml`, `/app/environment/plans/mid_halt.toml` (checkpoint after pass 1), `/app/environment/plans/mid_halt_split.toml` (adds continue checkpoint after pass 2).

## Artifacts

`/app/output/run_transcript.jsonl` — `seq`, `job`, `phase`, `slot`, `payload_digest`, `pass_index`.

`/app/output/pass_records/pass_<n>.json` — `stream_fingerprint`, `open_slots`, `mode`.

`/app/output/vault/manifest.json` — `last_generation`, `last_pass`, `open_count`. At a checkpoint boundary, `open_count` must equal the number of entries in that pass record's `open_slots`.

## Fingerprints

`payload_digest`: sha256 hex over little-endian `f64` draw bytes from the plan.

`stream_fingerprint`: first 16 hex chars of sha256 over UTF-8 `pass:{pass_index};slots:{sorted_slots_csv}`. The pass `mode` field records the run profile but is not hashed.

`slot_balance`: JSONL `spawn` events minus vault `open_count` at end; completed runs also satisfy spawn minus window times step events equals zero.

Gauge stdout (`gauge l2=… within=…`) is diagnostic only.
