# out_h6.json emission contract

Driver entry: `/app/tooling/run_h6.sh` (dual cred chain: cold cred a then warm cred b). Optional env toggles: `H6_RESET=1` clears var state before the chain; `H6_WARM_ONLY=1` reruns warm cred b while prior output remains.

## Top level

- `meta.run_tag`, `meta.cred_tag`, `meta.lane_a_win`, `meta.lane_b_win`
- `rows[]`, `ckpts[]`, `roll_fp`, `phase_wm`, `sweep_wm`

## Row fields

`lane_id`, `nat_key`, `bind_w`, `sweep_gen`, `phase_code`, `span_hi`, `ance_code`, `wit_fp`, `evt_stamp`, `row_kind`, `marker_lag`, `probe_scope`

## Checkpoint fields

`lane_id`, `sweep_gen`, `phase_code`, `span_hi`, `wit_fp`

## Fixture bindings

- `meta.lane_a_win` / `meta.lane_b_win` from `lane_a` / `lane_b` commit widths in `/app/environment/fixtures/grid_v2.dat`
- Each row `bind_w` equals the meta width for its lane without ancestry hop inflation
- After reset, cold pass `span_hi` values match `lane_a_span` and `lane_b_span` in `/app/environment/fixtures/snap_v2.dat`
- Warm cred b sets every lane B row `marker_lag` to the highest `lag` in `/app/environment/fixtures/lag_epoch_profiles.json` whose `ticket` is less than or equal to the active cred ticket (zeroing `marker_lag` is not valid)
- `sweep_wm` must not exceed the `cells` ceiling from grid_v2.dat

## wit_fp

First 16 hex chars of SHA256 over `lane_id|nat_key|sweep_gen|ance_code|bind_w` joined by pipe characters. Reference helper: `/app/environment/tooling/wit_check.sh` with the pipe joined string.

## roll_fp

Sort rows on `lane_id` then `nat_key`. Walk `wit_fp` bytes with `acc = acc * 131 + byte` mod 2^48, xor `sweep_gen << 16`, xor `phase_code << 8`, format `acc` as 16 lowercase hex digits.

## probe_scope

Sum, across all rows in both lanes, of the ASCII code of the first hex character of that row's `wit_fp` string (for example `ord(wit_fp[0])` in Python, or `wit_fp[0]` as a byte in Go), modulo one million. Every emitted row carries the same `probe_scope` value.

## Cred and row rules

- Cold cred a: `bind_w` 4 on every lane A row, `bind_w` 6 on every lane B row
- Warm cred b: `phase_code` 3 on every lane B row (profile `marker_lag` is non zero for the active ticket)
- Warm lane B emit aborts when lane A checkpoint `span_hi` from the cold pass no longer matches live lane A `span_hi`
- After `H6_RESET=1`, the first dual chain keeps `row_kind` live for nat_key 10 on lane A
- The next dual chain without another reset emits that same key as `row_kind` void with `sweep_gen` at least five
- `H6_RESET=1` must clear all var state so a later first chain cannot inherit a prior settled void
