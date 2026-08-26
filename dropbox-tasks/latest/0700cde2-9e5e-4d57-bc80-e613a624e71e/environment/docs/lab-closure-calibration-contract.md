# Lab closure calibration contract

ConchingAssay::WalkMath reconstructs a beta-six lattice chronicle so DSC peak capture, torque residuals, polymorph seals, and the published chronicle report agree.

## Closure invariants

1. Peak capture includes HOLD events whose temperatures fall inside a conching window. Shear at or above shear_bonus_hz adds ten percent integer duration to effective_hold_s.
2. Residual score per batch sums abs(temp_c - window midpoint) times effective_hold_s times quench_scale from the formulation catalog, plus hold-adjacency_contrib for that batch from /app/state/hold-adjacency-ledger.json, then rounds that sum to three decimal places before encoding and before snapshot_digest.
3. Dominant polymorph is the ranked hold accumulator that meets hold_min_s, with alphabetical break on equal accumulates.
4. Emit reads the state snapshots, hold ledgers, concordance artifacts, and bind manifest window path only. It must not reload kiln JSONL during emit. Residual scores on the published chronicle come from on-disk torque-residual-snapshot rows under the asymmetric trust rule.
5. Pairwise concordance closes residual distance against shared hold support; the cycle basis closes every lexical batch triple against its three staged pair edges.
6. Phase seal binds the capture, residual, epoch, manifest, hold ledgers, pair concordance, cycle basis, audit commitment, and derived bundle digests in the order defined by /app/docs/walk-seal-bind.md. Across epoch advances with unchanged walks, walk_content_digest stays stable while chronicle_digest changes.

## Related

- /app/docs/scientific-computing-workflow.md
- /app/docs/walk-seal-bind.md
- /app/spec/chronicle-output-v1.md
