# d8 observation contract

`/app/output/d8_observations.json` is one JSON object with keys `profile` (string, value `security_authority_split`), `rows` (array), and `gate_digest` (string). A full pipeline run produces one row per case entry across all case replays in `/app/docs/d8_run_notes.md` (6 rows: 2 each for `c_row_a`, `c_row_b`, and `c_row_c`).

Each replay batch evaluates two fixture role entries in list order (`entry_idx` 0 then 1). After a correct repair, each batch emits exactly one denied row and one accepted row. The source-mask batch (`c_row_a`) must deny `entry_idx` 0 and accept `entry_idx` 1. The cap-retention batch (`c_row_b`) must deny `entry_idx` 0 and accept `entry_idx` 1. The delayed-carry batch (`c_row_c`) must deny `entry_idx` 0 and accept `entry_idx` 1. Trap semantics below explain why those entries deny; the companion entry in each batch must accept with coordinated grant assembly, bounding refresh, lane revalidation, live-accept reporting, and per-batch lane-carry reset.

## gate evaluation versus emission

`gate_code` and `role_sample` are decided while `h2_runner` evaluates each fixture entry (grant mask assembly, bounding refresh, lane scan, and row matching). Those values are recorded in `/app/var/d8_raw.jsonl` before `q1_emit` builds observation rows. Observation emission must reflect the recorded gate decision and live accept snapshots from pivot probes. Zeroing mask fields on denied rows is required but cannot substitute for correcting upstream accept/deny decisions on trap entries.

Case entries pair a role name from the simulated fixture with a target row loaded from the fixture directory. Role-sample probes read a pivot line from `/app/work/pivot/<pivot>.txt` named on each replay line in `d8_run_notes.md`; pivot lines must be reloaded per case batch and must not be reused across batches when the pivot key changes.

Target rows are a single trimmed token per fixture `tgt.te` `ROW:` line. Role comparison is exact byte match on the active role buffer length; partial C-string prefixes must not satisfy a shorter row token when additional bytes follow an embedded zero byte.

Each row object contains:

| field | type | meaning |
|-------|------|---------|
| `case_id` | string | replay batch id (`c_row_a`, `c_row_b`, or `c_row_c`) |
| `entry_idx` | integer | zero-based index within the case role list |
| `role_text` | string | role name text used in the observation row |
| `line_text` | string | target row text from the fixture |
| `gate_code` | string | one character: `A` when the gate accepts the role, `D` when it denies |
| `cfg_mask` | integer | unsigned 32-bit tag recorded for configured state at load |
| `sample_mask` | integer | unsigned 32-bit tag from the role-sample reading for the entry |
| `live_mask` | integer | unsigned 32-bit tag from the live listing for the entry |
| `role_sample` | string | target row token text that satisfied matching |
| `row_digest` | string | eight lowercase hex digits derived below |

## raw trace epoch

`/app/var/d8_raw.jsonl` records one JSON object per evaluated entry. Each object includes `epoch` (unsigned integer) and `pivot` (string pivot key). `h2_runner` resets epoch to zero at the start of a run, then bumps epoch once per case batch before writing that batch's entries. Epoch values must strictly increase across batches in replay order (1, 2, 3 for the three batches).

## pivot journal

`/app/var/d8_pivot.jnl` records one JSON object per case batch replay in order. Each line contains `batch` (unsigned integer matching the batch epoch) and `pivot` (string pivot key from the replay line). The journal must list `k_a`, then `k_b`, then `k_c` in replay order.

## lane carry

Hop evaluation folds each entry's lane descriptor into a carry register that is ORed into the post-bound mask during lane scan. A lane-history register also records every folded descriptor and is combined when evaluating post-bound masks and capability bounding refresh. Both the carry register and the lane-history register must be cleared at the start of every case batch before any entry in that batch is evaluated. Stale carry or lane history from an earlier batch must not influence later batches.

## pivot accept cache

Role-sample probes may cache accept snapshots during emission for performance. Cached snapshots must be keyed by both pivot name and role text. Cache invalidation must run at each case-batch boundary in the hop runner before entries are evaluated, and again before emission replays raw rows.

## row_digest

Let `line_body` be UTF-8 text:

`case_id` + `|` + decimal `entry_idx` + `|` + `gate_code` + `|` + decimal `cfg_mask` + `|` + decimal `sample_mask` + `|` + decimal `live_mask` + `|` + `role_sample`

`row_digest` is the first eight hex digits of sha256(`line_body`).

## gate_digest

Sort rows by `case_id` ascending, then `entry_idx` ascending. Collect each row's `row_digest` in that order, join with newline (`\n`). `gate_digest` is the full lowercase hex sha256 of that UTF-8 blob.

## stamp replay

After `q1_emit` completes, `/app/var/d8_stamp.txt` contains one line: the `gate_digest` string with a trailing newline. Re-running `q1_emit` on unchanged raw input must rewrite the same stamp and observation digest.

## verifier digests

Platform tests recompute row and unit digests by piping bytes through `/app/environment/lib/digest_check.py`, which applies the sha256 rules above. Scoring reruns pytest with `--ctrf /logs/verifier/ctrf.json` after rebuilding via `make -C /app/environment all -j2`; agents are judged on regenerated observations, not harness telemetry.

## denied row emission

When `gate_code` is `D`, observation rows must set `cfg_mask`, `sample_mask`, and `live_mask` to zero. `row_digest` is computed from those zero mask fields together with the row identity fields above.

## cross-surface agreement

After a correct repair, raw trace `gate_code` and `role_sample` fields match the corresponding observation row fields. For each accepted row (`gate_code` `A`), `cfg_mask`, `sample_mask`, and `live_mask` are equal and match the tag derived from `role_text`, the pivot line for that case batch, and the matched token slot. For each denied row (`gate_code` `D`), all three mask fields are zero as in denied row emission. Source-mask traps must read `D` when only a source-residue mask would admit the lane. Cap-retention traps must read `D` when bounding refresh and lane revalidation disagree. Observation masks must reflect role-sample readings, not listing tags alone. When the same role name appears in multiple batches with different pivot keys, emission must reload the pivot line for that batch rather than reuse a prior batch's accept snapshot.
