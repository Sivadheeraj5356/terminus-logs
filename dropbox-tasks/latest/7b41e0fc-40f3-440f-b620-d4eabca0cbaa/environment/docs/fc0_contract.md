# m6_ctl matrix-all contract

Run:

`m6_ctl matrix-all`

Writes:

- `/app/output/bw_emit.json`
- `/app/output/stream_sidecar.bin`

State under `/app/var/`:

- `journal_tail.json` — `{journal_seq, receiver_tail}`
- `checkpoint.json` — `{lanes_witnessed, last_lane_id}`
- `wrap.gen` — unsigned wrap generation counter (single integer, whitespace trimmed)

Lane cache directory: `/app/var/lane_cache/`

Lane inputs: `/app/data/lanes/*.json` with fields
`lane_id`, `source_chain`, `receiver_chain`, `metadata_edges`,
`candidate_parents`, `interrupted`, `retry_overwrite`, `content_match`, `wrap_epoch`.

Reload overlays: `/app/data/reload/*.json` merge onto a lane and trigger a second witness pass.

## Report root

```json
{
  "rows": [{"lane_id","chain_stamp","parent_pick","rc_band","sync_label","stream_tag"}],
  "summary": {"rows_total","span_band","lineage_digest","sync_label","journal_seq","wrap_epoch"}
}
```

Rows are sorted lexicographically by `lane_id`. Exactly one row per bundled lane id.

## Row formulas

`source_tail` — last element of `source_chain`.

`receiver_tail` — journal anchor after incremental send apply for the lane (see **Journal anchor apply** below).

`parent_pick` — metadata-graph parent resolution from `metadata_edges` and `candidate_parents` (see **Parent pick resolution** below).

### Journal anchor apply

When applying incremental send for a lane, update the journal `receiver_tail` sidecar before deriving row fields. Let `chunk_anchor` be the last element of `receiver_chain` and `interrupted_anchor` the element at index `max(len(receiver_chain) - 2, 0)`.

When `interrupted` is true, the anchor is `interrupted_anchor` regardless of other flags. When `interrupted` is false and `retry_overwrite` is true, the anchor is `chunk_anchor`. Otherwise the anchor is `chunk_anchor`.

### Parent pick resolution

Build a directed map from `metadata_edges` (`[child, parent]` pairs). When the map contains `source_tail`, let `expect` be its mapped parent.

When `expect` is defined and `expect` appears in the lane's `candidate_parents` list (match against the fixture's original order): `parent_pick = expect`. Otherwise `parent_pick` is the first entry in `candidate_parents`, or empty string when the list is empty.

The fixture's `candidate_parents` order is authoritative; do not reorder or sort the list before applying this rule.

`chain_stamp` — eight lowercase hex digits: FNV-1a 32-bit hash of
`source_tail + "|" + receiver_tail + "|" + parent_pick`.

`rc_band` — `0` when `source_tail == receiver_tail == parent_pick`; otherwise
`(first four hex digits of chain_stamp parsed as u32) % 900 + 100`.

`import_ok` — `true` when `content_match` is true.

`chain_aligned` — `true` when `source_tail`, `receiver_tail`, and `parent_pick` are all equal.

`replay_ok` — `import_ok && chain_aligned`.

`sync_label` — `steady` when `rc_band == 0` and `replay_ok`; otherwise `drift`.

`stream_tag` — unsigned 32-bit mix of `lane_id`, `wrap_epoch`, `source_chain` links,
`interrupted`, and `retry_overwrite` using FNV-1a combining steps.

## Summary formulas

`rows_total` — count of row objects.

`span_band` — max `rc_band` minus min `rc_band` across rows.

`lineage_digest` — eight lowercase hex digits: start with `journal_seq ^ wrap_epoch`,
then for each row `chain_stamp` parse as u32 and add with rotate-left-5 fold. The fold walks rows in the same ascending `lane_id` order used for the emitted `rows` array (not reverse order, not hash-map iteration order, not witness-pass order).

`sync_label` — `steady` only when every row has `sync_label == steady`; otherwise `drift`.

`journal_seq` — incremented by row count after the matrix pass completes.

`wrap_epoch` — maximum of global `wrap.gen` and all lane `wrap_epoch` values touched.

## Checkpoint sidecar

After matrix-all, `checkpoint.json` records progress from the emitted report:

- `lanes_witnessed` — equals `summary.rows_total`.
- `last_lane_id` — `lane_id` of the final row in the ascending sorted `rows` array.

## Lane cache

Cache key materialization: `lane_id + "|" + wrap_epoch` (string). See `report_fields.toml` `[cache]` for lookup rules.

On open, the cache may rehydrate JSON sidecars from `/app/var/lane_cache/*.json` (filename stem is the lane id). Rehydrated entries participate in lookup only when keyed with the epoch-aware materialization above; a reload overlay that bumps `wrap_epoch` must recompute the row rather than reuse an entry stored under a prior epoch.

Lookup is an exact match on the materialized key. Do not serve a row keyed under a different `wrap_epoch` for the same lane id.

## stream_sidecar.bin sidecar

The stream sidecar binary format is defined as:

1. Magic `SWTB` (4 bytes)
2. Row count as little-endian `u32`
3. Per row: null-terminated `lane_id`, then `stream_tag` le-u32, `rc_band` le-u32,
   `chain_stamp` first eight hex digits as le-u32

## Witness pass order

1. Witness every bundled lane file in lexicographic path order (populate cache and advance the journal sidecar).
2. Apply each reload overlay and re-witness that lane (replace the prior row; cache must respect epoch).

Reload overlays must run only after every base lane pass completes. Running an overlay before its base lane pass would leave stale epoch-one rows in the final report.

## Recovery before re-verify

When repeating verification after a partial matrix pass, remove `/app/var/lane_cache/` and both output files, then rerun `m6_ctl matrix-all`. Journal and checkpoint seeds under `/app/var/` are reloaded from the image unless modified by a prior coherent pass.
