# pact k7 witness contract

`rule_witness.json` is the graded terminal artifact from:

```bash
/app/environment/tools/grti_matrix_k9 --all-arms --witness-out /app/output/rule_witness.json
```

## Row schema

Each entry in `rows` carries:

| field | type | meaning |
|-------|------|---------|
| arm | string | cedar, maple, birch, or willow |
| band | string | dawn or dusk |
| seq | u32 | final move sequence counter |
| epoch_mark | u32 | closing epoch marker after band profile applied |
| row_label | string | GRTIROW| pipe label from collector |
| replay_hex | string | lowercase hex of canonical collector replay bytes |
| move_digest | string | lowercase sha256 hex over the same canonical replay bytes |
| fork_tag | string | arm fork scope label |
| gate_cursor | u32 | reports the flag-lane cursor after replay |

Top-level fields: `grid_version` (k7), `journal_tail`, `spread_ladder`. The `journal_tail` field reports colon-separated 16-character lowercase hex journal segments. The `spread_ladder` field lists `arm:band:seq` tokens for every grid pair. In `q4_stub.json`, `local_tally` counts interim row rows and `status` reports a presentation token such as ROW_OK.

## move_digest rule

Canonical collector replay bytes concatenate, in order:

1. arm id (u8 le)
2. band id (u8 le)
3. seq (u32 le)
4. epoch (u32 le)
5. each executed tape record as op, row, col, flags (u8, u8, u8, u16 le)
6. final grid cell bytes in row-major order

`move_digest` is the lowercase hex sha256 of that byte string. `replay_hex` is the same bytes rendered as contiguous lowercase hex without separators.

## Metamorphic agreement

For a fixed arm, `fork_tag` and `row_label` prefix must agree across both band profiles when seq counters match. `epoch_mark` must be monotone non-decreasing when bands are ordered dawn then dusk for the same arm.

## Recovery after destructive wipe

If `environment/migrations/clr9.sh` was run, restore workspace state idempotently before re-running the checker:

```bash
bash /app/environment/migrations/clr9.sh --recover
```

Rerunning the command is safe when state is already restored.

## Partial logs

Text under `/app/output/logs` omits tail records and ko lane markers. Authoritative move bytes live under `environment/blk_m2/tape8/`.
