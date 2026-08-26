# Seal K4 packing rules

Offline pharmacy conformal-prediction evaluation packing for `/app/output/readiness_gonogo_brief.json`.
The model-risk desk uses frozen calibration annexes, nonconformity-linked segment vectors, and held-out board-pair packs to stress adversarial generalization of uncertainty briefs. This is an ML evaluation contract (coverage / calibration / OOD held-out), not a generic ETL transform.

## Command

```
/app/environment/scripts/run_k4.sh --root /app/environment/data/pack_tr --out /app/output/readiness_gonogo_brief.json
```

Build first with `/app/environment/scripts/build_k4.sh` when evaluator sources change. The conformal scoring pipeline is driven by `/app/environment/src/cmd/desk_run.ts` with supporting modules under `/app/environment/k4/` and `/app/environment/n8/`. Workspace files include `/app/environment/k4/x2/x2_mux.ts`, `/app/environment/k4/x3/frag_buf.ts`, `/app/environment/n8/q1/ops_mux.ts`, and `/app/environment/n8/q4/pack_emit.ts`. Runtime root is selected by `--env` or the `K4_ROOT` environment variable (default `/app/environment`).

Desk observables:

```
/app/environment/tools/obs_k4 --env /app/environment
```

`obs_k4` walks `/app/environment/data/xp/*.pack`, rebuilds a temporary root per pack, and prints a single line `obligation_violations=<int>`. Success requires `0`.

## Output schema

Top-level object, `schema_ver` must be `1`.

The `brief_digest` field must be a 64-char lowercase hex SHA-256 over the canonical payload defined below. Hex digits must be drawn from `0123456789abcdef` only.
The `gate_rows` field must be an array of gate row objects.
The `rb_rows` field must be an array of rollback trigger row objects (one per gate row, same order).
The `seg_trace` field must be an object with `vec`, `stamp`, and `fam`.

Gate row object fields:

The `row_id` field must be `g0`, `g1`, ... in emit order.
The `board_pair` field must be `LEFT|RIGHT` from the root pack manifest or xp pack.
The `clause_ids` field must be sorted unique clause ids after lattice join.
The `seg_vec` field must be the conformal segment vector after annex rebind.
The `disc_bind` field must be sorted unique clause ids kept under active board authority.
The `gate_kind` field must be `go` when `disc_bind` is non-empty and sum(`seg_vec`) > 0, else `nogo`.

Rollback trigger row object fields (`rb_rows`):

The `trig_id` field must be `t0`, `t1`, ... matching gate row index.
The `metric_fam` field must equal `seg_trace.fam` after the active annex selection.
The `bind_stamp` field must equal `seg_trace.stamp`.
The `hx_ref` field must equal `brief_digest`.

`seg_trace` fields:

The `stamp` field must be the maximum `stamp` across `/app/environment/data/cal/bind_*.json`.
The `fam` field must be the `fam` of the bind sheet that owns that maximum stamp.
The `vec` field must be that sheet's `vec` array (annex rebind ignores stale input vectors).

Pack net JSON under `wk/` may include a `seed_cids` field: that field must list the seed clause ids for the net before lattice join expands them.

## Lattice join

Inputs: rotation key `K` from the pack (`rot`), seed clause list `P`, bind stamp `S` (unused for membership, retained for call shape).

1. Resolve the board pair whose `rot` equals `K` from `/app/environment/data/hold_tbl.toml` (`[train]` or `[pairs.kNN]`).
2. Load `/app/environment/data/long_ctx/ledger_mfest.toml`. Collect every `cids` entry for shards whose `board` is either side of that pair.
3. Output = sorted unique union of `P` and those ledger cids.

## Annex rebind

Inputs: candidate vector `T`, stamp `S`, family `F`.

1. Among `/app/environment/data/cal/bind_*.json`, pick the sheet with the greatest `stamp` that is `<= S`. If none, pick the sheet with the least `stamp`.
2. Output that sheet's `vec`. Do not return `T` once a sheet is selected.
3. `F` must equal the selected sheet's `fam` when forming `seg_trace.fam`.

When a bind sheet's `stamp` advances past a prior maximum, the selected vector must change on the next rebuild.

## Disclosure authority

Inputs: `board_pair` string `LEFT|RIGHT`, clause list `C`.

1. Look up the pair in `hold_tbl.toml` and read its `active` board code.
2. Keep clause ids whose board prefix (substring before the first `.`, uppercased) equals `active`.
3. Output sorted unique.

Training and held-out packs may share seed shapes; authority follows `active`, not the left-hand board.

## Rollback metric family

After annex selection, rollback trigger rows must carry the post-selection `fam` from the winning bind sheet. Training-era family `1` from `bind_a` is not valid once `bind_b` owns the maximum stamp.

## brief_digest

Canonical payload is JSON with keys `gate_rows` then `seg_trace` only (no `schema_ver`, no `brief_digest`, no `rb_rows`). UTF-8 bytes of that object hashed with SHA-256, lowercase hex. After the digest is known, each `rb_rows[].hx_ref` is set equal to `brief_digest`.

Consecutive identical runs with identical inputs must yield the same `brief_digest`.

## Held-out packs

Files under `/app/environment/data/xp/*.pack` are opaque pair packs. Each begins with magic `K4P1` then one JSON object: `kid`, `pair`, `rot`, `active`, `seed_cids`. Obligation checks synthesize a pack root from that object plus the shared long_ctx and cal trees. Do not hand-edit `/app/output/readiness_gonogo_brief.json`; rebuild through `run_k4.sh`.
