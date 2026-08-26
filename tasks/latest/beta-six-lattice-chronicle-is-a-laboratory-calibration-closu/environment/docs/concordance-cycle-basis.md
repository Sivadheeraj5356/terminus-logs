# Concordance cycle basis

Bind lifts pairwise concordance into `/app/state/concordance-cycle-basis.json`. The artifact records every three-batch simplex so that shared thermal support and the three staged pair edges close as one analytical object.

## Cycle rows

Start with captured batches in lexical `batch_id` order and emit one row for every combination `a < b < c`. Rows therefore follow combination order.

- `batch_ids` is `[a,b,c]`.
- `common_polymorphs` is the sorted intersection of polymorph names present in all three hold-profile lists.
- For each common polymorph, total `effective_hold_s` independently in each batch. `common_effective_hold_s` is the sum of the smallest of those three totals.
- `edge_pairs` is `[a|b,a|c,b|c]`.
- `edge_scores` contains the corresponding staged `concordance_score` values in that order. These values are not re-derived from torque residuals.
- `edge_commitment` is lowercase SHA-256 over canonical compact JSON of three objects with keys `pair` and `score`, in `edge_pairs` order.
- `cycle_mean` is the arithmetic mean of `edge_scores`, rounded to six decimal places. With no edges it is 1. Whole numbers use the Perl JSON::PP integer encoding rule.

The top-level keys are `schema`, `rows`, and `cycle_digest`; schema is `concordance-cycle-basis-v1`. `cycle_digest` is lowercase SHA-256 over canonical compact JSON of `schema` and `rows`.

## Emit validation and seal

Emit verifies the artifact digest and re-derives batch triples, common polymorphs, and common hold totals from peak capture. It validates each edge commitment and cycle mean against the staged concordance artifact. This validation consumes concordance values as staged data and does not recompute them from the residual snapshot.

The phase seal carries `cycle_digest`. `topology_bundle_digest` is SHA-256 over `concordance_digest|cycle_digest`; `closure_bundle_digest` is SHA-256 over `ledger_triad_digest|topology_bundle_digest`. Missing cycles, changed rows, a stale edge commitment, or a digest mismatch must fail emit before report replacement or epoch advancement.
