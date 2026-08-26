# Public contract

## Glossary

- `peer_id`: row field naming a logical peer; primary peers are the non-mirror entries in `peer_ids.txt` (mirror peers use an `_m` suffix).
- `shift_code`: per-row divergence magnitude; coherent runs keep this at `0`.
- `conv_label`: terminal workflow label; coherent runs read `settled`.
- `range_band`: maximum absolute `shift_code` across rows.
- `flow_digest`: see module comment in `/app/environment/engine/src/wg_run.cpp`.

## Reconcile report

The report at `/app/output/psk_rotate_report.json` must contain `rows` and `summary`. Each row records `mux_rc`, `mark_rc`, `ov_rc`, `seal_rc`, `shift_code`, and `bind_hex` (exactly 16 lowercase hexadecimal digits). The summary records `rows_total`, `conv_label`, `range_band`, and `flow_digest`. The witness artifact at `/app/environment/w8g/staged/w8_chain.bin` must embed bind material when `seal_rc` passes.

## Coherence predicates

Mirror peer pairs (`peer_a`/`peer_a_m`, `peer_b`/`peer_b_m`) must agree on `bind_hex` and the four rc fields when coherent.

Coherent runs require every row to have `mux_rc`, `mark_rc`, `ov_rc`, and `seal_rc` equal to `1`, `shift_code` equal to `0`, and `conv_label` equal to `settled`.

## Workflow

1. Run stage profile to emit durable mux token under `/app/environment/w8g/staged/`.
2. Run apply profile with `--hook replay` and a `variant-seed` from `perm_tbl.toml`.
3. Validate `/app/output/psk_rotate_report.json`, `/app/output/run_traces/phase.jsonl`, and the staged witness bytes.

The stage profile writes opaque staged bind material under `/app/environment/w8g/staged/`. Apply replay must converge to settled mux state from that staged material. Terminal coherence requires the reconcile report, run traces, and witness bytes to agree after the full two-phase workflow.

## Sparse experiments

Only peers listed in `trace_subset.txt` satisfy convergence spot-check claims.

Sparse phase traces under `/app/output/run_traces/phase.jsonl` record workflow markers including `epoch`, `mux`, and `mark` before per-peer row events.

## Permutation table

`/app/environment/data/perm_tbl.toml` assigns per-seed weights and a `route_mark` used by route selection. Changing seed weights must change bind material and `flow_digest`.

## Determinism

Consecutive pipeline runs produce identical reports when source and data tables are unchanged.

## Recovery

After drills in `recovery_tbl.toml`, restore durable artifacts from `/app/environment/w8g/durable/` and rerun the full workflow; terminal reconcile must match the pre-drill coherent outcome.

## Status view semantics

`--status-view` must independently confirm terminal reconcile coherence across:

1. reconcile JSON rows (`conv_label` settled with coherent rc fields),
2. run traces under `/app/output/run_traces/phase.jsonl` (including `epoch`, `mux`, and `mark` markers), and
3. witness bytes at `/app/environment/w8g/staged/w8_chain.bin` (bind material for sealed rows).

It must not claim `settled` from the JSON alone, from stage-only intermediate rows, or when witness or trace material has been corrupted after a previously coherent run.

## Rare vocabulary

Status-view labels map to entries in `/app/environment/docs/glossary.txt`.
