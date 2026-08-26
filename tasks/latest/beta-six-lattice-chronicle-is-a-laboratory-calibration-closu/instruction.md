Beta-six lattice chronicle is a laboratory calibration closure over differential scanning calorimetry hold peaks and conching kiln torque microsegments. Under /app the assay shell already builds and the working LabAssay catalog inventory summarizes formulation fixtures. Implement the numerical DSC-torque closure kernels that polymorph-chronicle loads for bind, emit, and fuse so the assay publishes a scientifically closed lattice chronicle.

The kernels load kiln-run traces and the conching window table, materialize DSC peak-capture, hold-adjacency, torque residual, cross-batch concordance, and concordance-cycle snapshots, seal polymorph transitions with the staged closure digests, and publish the lattice chronicle report. Residual scores, consecutive HOLD adjacency gap coupling, pairwise and triple-wise polymorph closure, dominant polymorph selection with hold_min_s, quench_scale, walk content digests, and emit-from-staging rules follow the lab contracts below. Do not use flavor scoring under /app/lib/decoy/ for chronicle publish.

Operator commands: /app/docs/assay-operator-commands.md and /app/docs/bind-emit-stage.md. Workflow and closure math: /app/docs/scientific-computing-workflow.md and /app/docs/lab-closure-calibration-contract.md. Trace, seal, spine, adjacency, concordance, cycle-basis, and report schemas: /app/docs/kiln-trace-contract.md, /app/docs/walk-seal-bind.md, /app/docs/hold-spine-ledger.md, /app/docs/hold-adjacency-ledger.md, /app/docs/cross-batch-concordance.md, /app/docs/concordance-cycle-basis.md, /app/docs/lattice-chronicle-schema.md, and /app/spec/chronicle-output-v1.md. Digest fragment helpers live under /app/helpers/.

Primary analytical artifacts:
/app/state/dsc-peak-capture.json
/app/state/torque-residual-snapshot.json
/app/state/hold-spine-ledger.json
/app/state/hold-adjacency-ledger.json
/app/state/cross-batch-concordance.json
/app/state/concordance-cycle-basis.json
/app/state/polymorph-walk-seal.json
/app/state/chronicle-bind-manifest.json
/app/output/lattice-chronicle-report.json
/app/var/walk_epoch
/app/var/chronicle-audit.log.jsonl

The lattice chronicle report must include chronicle_digest, walk_content_digest, and per-walk quench_scale under the schema rules.
