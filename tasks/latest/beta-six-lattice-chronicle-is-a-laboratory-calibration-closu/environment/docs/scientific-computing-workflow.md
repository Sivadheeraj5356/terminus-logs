# Scientific computing workflow — beta-six lattice chronicle

This assay is a numerical simulation and lab calibration closure. Operators implement ConchingAssay::WalkMath kernels that correlate DSC hold peaks with conching kiln torque residuals, then publish a sealed lattice chronicle report.

## Working baseline

LabAssay::CatalogInventory under /app/lib/LabAssay/ already inventories formulation catalog fixtures via polymorph-chronicle inventory. That command works without ConchingAssay::WalkMath.

## New scientific subsystem

ConchingAssay::WalkMath modules under /app/lib/ConchingAssay/WalkMath/ perform:

1. Trace load in batch_id, cycle_seq, then ts order (MARKER events excluded).
2. Peak capture with shear-bonus hold scaling and capture_digest over canonical JSON.
3. Consecutive hold adjacency and lattice residual scores: midpoint temperature deviation times effective_hold_s times formulation quench_scale, with the batch total rounded to three decimal places before snapshot digests.
4. Pairwise batch concordance followed by the triple concordance cycle basis.
5. Bind manifest with kiln_traces_path, conching_window_path, and bind_digest over those paths.
6. Hold-spine ledger with contiguous spine_seq rows and spine_digest over capture holds.
7. Emit from on-disk staging only: verify the staged closure ledgers, seal pair and cycle topology, select dominant polymorph with the hold_min_s gate, publish both report digests, bump epoch, and append audit.

Primary artifact: /app/output/lattice-chronicle-report.json after fuse.

Contracts: /app/docs/assay-operator-commands.md, /app/docs/bind-emit-stage.md, /app/docs/lab-closure-calibration-contract.md, /app/docs/walk-seal-bind.md, /app/docs/hold-spine-ledger.md, /app/docs/cross-batch-concordance.md, /app/docs/concordance-cycle-basis.md, and /app/docs/lattice-chronicle-schema.md.
