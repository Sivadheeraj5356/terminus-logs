# Assay operator commands — polymorph-chronicle

Shared flags: --lattice-invariant-catalog PATH points at formulation-catalog.json --conching-window PATH points at the conching window table. --kiln-traces DIR points at a directory of kiln run batches that may also contain non-trace JSON sidecar files. Only *.jsonl files in that directory are loaded as traces per /app/docs/kiln-trace-contract.md. --output PATH is the lattice chronicle report path for emit and fuse.

## inventory

Working baseline. Summarizes formulation ids from the lattice-invariant catalog into an inventory JSON under /app/output when --output is set. Does not require ConchingAssay::WalkMath.

## bind

Requires ConchingAssay::WalkMath kernels under /app/lib/ConchingAssay/WalkMath/. Loads kiln traces and the conching window table. Writes peak capture, torque residual snapshot, and the bind manifest into /app/state. Honors TB3_KILN_TRACES and TB3_CONCHING_WINDOW when set.

## emit

Requires ConchingAssay::WalkMath. Reads bind peak-capture snapshots and manifest paths only. Must not re-load kiln traces. Writes the lattice chronicle report, appends chronicle audit JSONL, and advances walk epoch.

## fuse

Runs bind then emit with the same catalog, window, traces, and output paths.

Contract details for seal preimages and residual formulas live in /app/docs/walk-seal-bind.md and /app/docs/lab-closure-calibration-contract.md.
