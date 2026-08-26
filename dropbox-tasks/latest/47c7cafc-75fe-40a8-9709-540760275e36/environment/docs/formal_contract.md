# Ops row report contract

## Build and run

From `/app`:

```
/app/bin/hx_ctl run
```

Hook argv sequences for kill-resume and undo drills are listed in `docs/hook_cmds.txt`.

## Report shape

Output path: `/app/output/ops_row_report.json`

Primary unit ids are listed in `docs/prim_ids.txt`.

The report has `rows` and `summary`.

Each row records:

- `unit_id` (string)
- `bind_rc` (integer 1 when bind closure passes, else 0)
- `lock_rc` (integer 1 when lock closure passes, else 0)
- `unit_rc` (integer 1 when unit closure passes, else 0)
- `drift_code` (integer)
- `facet_hex` (exactly 16 lowercase hexadecimal digits)

The summary records:

- `rows_total` (integer; must equal the number of objects in `rows`)
- `sync_label` (string; must read `steady` when the run is fully coherent)
- `span_band` (integer; computed as defined in the `pilot/entry.rb` module header)
- `row_digest` (8 lowercase hex characters; computed as defined in the `pilot/entry.rb` module header)

## Mirror pairs

- `bind` with `bind_echo`
- `upper` with `upper_echo`
- `worker` with `worker_echo`

## Coherence

Coherent runs keep `drift_code` at 0 on every row, all three closure counters at 1, matching `facet_hex` on each mirror pair, and `sync_label` reading `steady`.

Incoherent runs break at least one of those conditions.

## Reduction

The module comment above `pilot/entry.rb` defines `span_band` and `row_digest` reduction. Read that header instead of hand-writing JSON.

## Helper API surfaces

The following helper APIs are part of the repair contract and must remain callable with these signatures:

- `M7k::StepMux.fn_m7(step_ix, family_ix, prev_family)`
- `R3p::CapFold.fn_r3(ctx, stamp_a, stamp_b)`
- `W9n::RevertArm.fn_w9(state, tree_a, tree_b)`

A conforming repair should fix these helpers rather than only shaping the final JSON in a wrapper. The driver may be exercised through hook drills that reveal whether muxing, publish gating, and revert behavior still affect the report.

## Ladder mux participation

For each ladder step, `fn_m7` contributes facet material from all three inputs: the step index, the current family index, and the previous family index. The family value is not a display-only parameter. If a ladder row changes `family_ix`, the affected unit facet and the final `row_digest` must be able to change.

The previous family value is the family index from the immediately prior step for the same unit, or 0 for the first step. The step mux result is folded into the unit facet path before `facet_hex` and `row_digest` are reduced.

## Hook drill coherence

Hook runs must derive coherence from the helper behavior above. A repaired normal run should be coherent. If the mux helper ignores family parameters, if publish gating exposes grants before activation, or if the revert arm fails to restore the generation state used by the byte-log witness, the resulting hook report should become incoherent by changing at least one closure counter, pair agreement, drift value, or sync label.

## Generalization

Held-out permutation scenarios live in `data/ord_table.toml`. A repaired host must pass every row in that file when driven with the documented hook argv patterns.
