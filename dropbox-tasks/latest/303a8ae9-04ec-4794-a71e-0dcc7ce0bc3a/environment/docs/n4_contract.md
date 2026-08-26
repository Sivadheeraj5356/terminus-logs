# PIT materialize contract

This contract is for the offline feature store that feeds model training. The
graded folds are training batches. Leakage here corrupts train metrics even when
a tiny holdout model looks healthy.

Build command

```
bash /app/environment/scripts/mk_all.sh
```

Materialize command

```
/app/environment/bin/pitctl materialize --fold <fold_id> --out /app/output/pit_report.json
```

Status command (not graded)

```
/app/environment/bin/pitctl status --fold <fold_id>
```

Verify command

```
/app/environment/bin/pitctl verify --fold <fold_id> --report /app/output/pit_report.json
```

## Fold inputs

Fold configs live under `/app/environment/data/cfgs/<fold_id>.json`.
Each fold JSON object includes `fold_id`, `watermark_ms`, `lag_ms`,
`event_pack`, `feature_packs`, and `remap_pack`.

Sample rows hold `event_id`, `entity_id`, and `event_ms`.
Remap rows hold `alias`, `canonical`, and `active_from_ms`.

Feature packs are ordered frame lists under
`/app/environment/data/features/<pack>.json`. Each frame is an object with
`op` set to `put` or `kill`.

- `put` carries a `rev` object with `rev_id`, `entity_id`, `valid_from_ms`,
  `ingested_ms`, `revoked`, and `values`.
- `kill` carries `rev_id` and marks that revision revoked when it already
  exists in the loaded pool.

Load every pack in listed order and apply frames left to right. A later `put`
with the same `rev_id` replaces the earlier body. `kill` only flips
`revoked` to true for an existing `rev_id`.

Feature `values` objects carry numeric fields such as `spend`, `tenure`,
`score`, and `bias`, depending on the pack.

## Alias resolution

Resolve a request id against the remap pack at the sample `event_ms`.

At each hop, consider only remap rows whose `alias` equals the current id and
whose `active_from_ms` is at or before `event_ms`. Among those rows pick the
greatest `active_from_ms`; ties keep the later row in pack order. Follow the
chosen `canonical` for up to eight hops. If a cycle appears before a fixed
point, keep the original request id unchanged. If no row qualifies, stop on
the current id. Fixture-only poison targets `poison_z9` and `dead_end_z` are
not valid resolved entities and must never appear in output rows.

## Selection policy

1. Resolve the sample `entity_id` through the fold remap pack as above.
2. Keep the sample `event_ms` as the clock input to selection. Lag is applied
   only when building the valid_from horizon below. Do not subtract watermark
   from the sample clock before selection.
3. Effective valid_from horizon is `event_ms` minus `lag_ms`.
4. A revision is a time candidate when its `entity_id` matches the resolved id
   and its `valid_from_ms` is at or before the effective horizon. Watermark is
   ignored for this list. Revoked revisions may still be time candidates.
5. A revision is selectable when it is a time candidate, `revoked` is false, and
   its `ingested_ms` is at or before `event_ms` plus `watermark_ms`.
6. Among selectable revisions pick the greatest `valid_from_ms`. Ties break by
   greatest `ingested_ms`, then by ascending `rev_id`.
7. If none are selectable, emit an empty feature row (`feat_rev` and
   `feat_hash` empty strings, `values` empty object) with policy `miss`.
8. Otherwise policy is `asof_wm`.

`asof_ms` on each output row stays equal to the original `event_ms` even when
`lag_ms` is nonzero.

Within one materialize pass, a memoized pick for one resolved entity must not
be reused for a later sample that shares the entity but has a different
`event_ms`.

## Output schema (`pit_report.json`)

Top-level fields must include `fold_id` (string), `row_count` (number),
`rows` (array), `audit_trace` (array), and `ledger_digest` (hex sha256).

`rows` must be sorted by `event_id` ascending. Each row must include
`event_id`, resolved `entity_id`, `feat_rev`, `feat_hash`, `asof_ms`, and
`values` (object with sorted keys).

`audit_trace` means the per-sample selection record array. It must be sorted
by `event_id` ascending. Each record must include `event_id`,
`request_entity`, `resolved_entity`, `candidate_revs` (sorted time-candidate
rev ids), `chosen_rev`, and `policy`. The chosen revision, when non-empty,
must appear in `candidate_revs`.

## Digests

`feat_hash` is computed as sha256 over the canonical JSON of an object with
keys `entity`, `rev`, and `values`, where `entity` holds the resolved entity
id, `rev` holds `feat_rev`, and `values` holds the feature object, with object
keys sorted recursively and no insignificant whitespace.

Row segment digest for a row is sha256 over the canonical JSON of an object
with keys `event_id`, `entity_id`, `feat_rev`, `feat_hash`, `asof_ms`, and
`values` (values keys sorted), no insignificant whitespace.

`ledger_digest` is sha256 over the canonical JSON of an object with keys
`fold_id` and `segs`, where `segs` is the array of row segment digests for
rows sorted by `event_id` ascending.

`feat_hash`, row segment digests, and `ledger_digest` are lowercase hex
encodings of sha256 digests. Each digest string is exactly 64 hex characters.

## Journal

After a successful materialize, write
`/app/output/.pit_journal/<fold_id>.json` with fields `fold_id`,
`ledger_digest`, `row_count`, and `seg_digests`. `seg_digests` must equal the
row segment digest array used to build `ledger_digest`. A second materialize
of the same fold must produce an identical report.

`pitctl verify` prints a JSON object with boolean `ok`, string `reason`,
string `journal_digest`, and string `report_digest`. When the journal matches
the report, including reconstructed digest from `seg_digests`, `ok` is true,
`reason` is `match`, and both digest fields equal the report `ledger_digest`.
When digests, row counts, or segment reconstruction disagree, `ok` is false
and `reason` is `journal_mismatch`. When the journal file is missing,
`reason` is `missing_journal`.

## Graded folds

Graded fold ids are `fold_a`, `fold_b`, `fold_c`, `fold_d`, and `fold_e`.
Their configs are `/app/environment/data/cfgs/fold_a.json` through
`/app/environment/data/cfgs/fold_e.json`.

`pitctl status` only prints pack counts. A zero exit from status is not
evidence that materialize matches this contract.

Static hand-written JSON under `/app/output` without rebuilding through
`mk_all.sh` and `pitctl materialize` is insufficient.
