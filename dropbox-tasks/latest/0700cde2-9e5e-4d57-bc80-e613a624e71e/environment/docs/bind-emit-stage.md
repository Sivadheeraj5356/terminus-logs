# Bind and emit stage contract

polymorph-chronicle exposes three subcommands:

- bind loads kiln JSONL traces and the conching window table, then writes /app/state/dsc-peak-capture.json, /app/state/hold-adjacency-ledger.json, /app/state/torque-residual-snapshot.json, /app/state/cross-batch-concordance.json, /app/state/concordance-cycle-basis.json, /app/state/hold-spine-ledger.json, and /app/state/chronicle-bind-manifest.json before emit runs
- emit reads the bind manifest, hold-spine ledger, hold-adjacency ledger, pair concordance, cycle basis, and on-disk peak-capture snapshots only. It must not reload kiln traces from disk during chronicle emit.
- fuse runs bind then emit and writes /app/output/lattice-chronicle-report.json as the chronicle artifact

During bind, when environment variable TB3_KILN_TRACES is set to an absolute directory path, trace load uses that directory instead of the CLI --kiln-traces value. When TB3_CONCHING_WINDOW is set to an absolute file path, bind uses that window table instead of --conching-window. The bind manifest must record the conching_window_path and kiln_traces_path actually used so emit can load the same window table for dominant polymorph scoring.

emit loads /app/state/dsc-peak-capture.json and /app/state/torque-residual-snapshot.json from the bind snapshot. It derives polymorph-walk-seal.json and the lattice chronicle publish from those artifacts plus the manifest window path. residual_score values on the chronicle come from the staged torque-residual-snapshot rows (see asymmetric trust in /app/docs/walk-seal-bind.md).

Stdout from emit or fuse must include a line beginning chronicle_digest= followed by the hex digest matching the lattice chronicle report at /app/output/lattice-chronicle-report.json after emit.
