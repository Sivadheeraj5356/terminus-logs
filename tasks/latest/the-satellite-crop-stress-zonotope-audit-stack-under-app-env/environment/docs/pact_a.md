# Row shape contract

## Command

```bash
/app/environment/tools/hs_run.sh --all-lanes --rotations /app/environment/docs/rot_d.toml
```

Rebuild first with `/app/environment/build.sh`. The same runner accepts an
optional `--warm` flag. A warm path must publish the same terminal digests,
nest spans, and seals as a cold regeneration when the stage cache seal is valid.

## Terminal artifact

`/app/output/audit_report.json` is the only graded deliverable. Files under
`/app/output/stage/` are intermediate operator echoes and are not graded as
success criteria, though the runner may write digest cache material there that
must stay coherent with the live rotation fingerprint and journal window seal.

## Schema

Top-level object fields

- `lane_ids` (array of string) - must match `/app/environment/data/id_list.txt` order
- `lanes` (array of objects), one per lane id, each with
  - `lane_id` (string)
  - `digest_hex` (string, lowercase sha256 hex, 64 chars)
  - `seg_order` (array of int) - annex ordinals used for that digest, ascending zero then one then two
  - `script_rows` (array of object) - each object has row_id (int), bind_ref (string), body (string)
  - `cite_pairs` (array of pairs) - each pair is row_id then bind_ref; must match script_rows bindings and ledger rows in store_q.sqlite
  - `nest_span` (array of float) - length four inclusion span vector
  - `nest_depth` (int) - must equal three
  - `alg_keys` (array of string) - fixture algebra keys after rotation arms have been applied to a fixpoint
- `run_digest` (string) - lowercase sha256 hex over canonical JSON of lanes with keys sorted, compact encoding
- `rot_arms` (array of string) - arm ids from rot_d.toml that were applied (all arms when --rotations is set)

## Phase outcomes

1. Materialize annex segment bytes under the stress journal rules in `data/wal44/` and compute win_seal
2. Apply precondition remaps from rot_d.toml to a fixpoint and derive a fold fingerprint from the remapped key set
3. Fold materialized segments against ledger keys into per-lane digests; digest cache entries must not survive when fingerprint or seal changes
4. Reduce zonotope inclusion after remaps have landed (bias tracks the remapped fingerprint text, not a raw start-set count)
5. Emit proof script rows bound to ledger row_id / bind_ref with sealed bodies
6. Write terminal audit_report.json

## Digests

Lane digest_hex obligations live with the annex fold notes. Segment bytes used
as fold input must be the journal-materialized bytes under wal44 watermark
windows, not bare annex zeros. The seal from the winning window is part of the
digest preimage and the cache key.

## Ledger

`/app/environment/data/store_q.sqlite` table pair_tab holds columns row_id
(integer) and bind_ref (text). Script rows and cite pairs must bind to these
durable identifiers. Each `script_rows.body` is the lowercase hex encoding of
the first four bytes of sha256 over the UTF-8 bind_ref string.

## Stage echo

`/app/output/stage/summary.json` may include a status field with value coherent
on default lanes. It is not graded. A stage digest cache file may exist beside
it; serving a cache hit whose fingerprint or seal does not match the live
remapped algebra set and win_seal is a terminal audit fault. Leftover resume or
materialization echo files under stage must not divert the next full
regeneration away from live journal materialization. Warm restarts that trust a
green stage summary without resealing are faults.

## Rotation arms

rot_arms lists every id from `/app/environment/docs/rot_d.toml`. Arms may form
chains; terminal alg_keys must reflect the fixpoint, not intermediate hops.
