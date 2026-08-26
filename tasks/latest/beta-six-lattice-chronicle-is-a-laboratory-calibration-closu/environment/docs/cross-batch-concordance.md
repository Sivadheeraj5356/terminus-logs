# Cross-batch concordance closure

Bind writes `/app/state/cross-batch-concordance.json` after the torque residual snapshot. Emit treats this as a staged analytical artifact and validates it against the peak capture and residual snapshot before publishing.

## Pairwise rows

For every unordered pair of captured batches, ordered first by `left_batch_id` and then `right_batch_id`:

- `shared_polymorphs` is the sorted intersection of polymorph names present in both hold-profile lists.
- For each shared polymorph, total `effective_hold_s` independently in each batch. `shared_effective_hold_s` is the sum of the smaller total for every shared polymorph.
- `residual_gap` is the absolute difference between the two staged residual scores, rounded to three decimal places and encoded under the Perl JSON::PP whole-number rule.
- `concordance_score` is `shared_effective_hold_s / (shared_effective_hold_s + residual_gap)`, rounded to six decimal places. When both terms are zero, the score is 1. Encode whole values as JSON integers.

Each row has exactly `left_batch_id`, `right_batch_id`, `shared_polymorphs`, `shared_effective_hold_s`, `residual_gap`, and `concordance_score`.

## Artifact and seal

The top-level keys are `schema`, `rows`, and `concordance_digest`; schema is `cross-batch-concordance-v1`. `concordance_digest` is lowercase SHA-256 over canonical compact JSON of `schema` and `rows` only.

The phase seal carries `concordance_digest`; the cycle-basis contract extends it with the triple closure. The final phase-seal preimage order is:

`capture_digest|snapshot_digest|epoch|bind_digest|spine_digest|adjacency_digest|concordance_digest|cycle_digest|audit_commitment|ledger_triad_digest|topology_bundle_digest|closure_bundle_digest`

Emit recomputes `concordance_digest` from the staged artifact and recomputes pair identities, shared polymorphs, and shared hold totals from peak capture. The residual-derived `residual_gap` and `concordance_score` remain bind-time staged values under the asymmetric residual trust rule in `/app/docs/walk-seal-bind.md`; their integrity is carried by `concordance_digest`, not by re-reading kiln traces. Missing rows, changed rows without a matching digest, capture-projection disagreement, or a digest mismatch must make emit fail without replacing the chronicle report or advancing the epoch.
