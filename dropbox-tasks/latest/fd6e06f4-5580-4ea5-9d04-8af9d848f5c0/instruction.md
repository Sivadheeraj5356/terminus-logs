# Feature Store Training Leakage and Model Deployment Gate

Certify each ML model training run stored in `/app/data/lineage.duckdb` before deployment:

1. **Feature leakage** — reject training runs that bind features whose store availability timestamp is after the training ledger cutoff (temporal leakage into the training window).
2. **Model registry gate** — reject training runs whose model artifact fails the live model-deployment registry check.
3. **Feature lineage** — for rejected runs, emit a Graphviz feature-lineage diagram of the training feature graph.

Repair `/app/src/feature_audit.c` so the training-compliance evaluator writes correct ML governance artifacts under `/app/output/`. Policy cutoffs, registry base URL, freshness column, violation detail templates, lineage digraph layout, and contract tokens are supplied by the live inputs under `/app/data/` (including `governance_policy.json`, the graph emission binding selected for this feature-store domain, and `contract_binding_requirements.json`).

```bash
make -C /app/src all
/app/bin/feature_lineage_verdict --evaluate-training-runs \
  --db /app/data/lineage.duckdb \
  --policy /app/data/governance_policy.json \
  --output /app/output
```

## Required outputs

Under `/app/output/`:

| File | Purpose |
|------|---------|
| `training_run_verdicts.json` | Per-run approve/reject with leakage and registry violation records |
| `leakage_findings.csv` | Flat findings for leaking features and unapproved models |
| `rejected_run_lineage.dot` | Feature-lineage Graphviz for rejected training runs |
| `training_compliance_contract.md` | Brief citing the live governance tokens required by `contract_binding_requirements.json` |

Only modify `/app/src/feature_audit.c`. On every evaluate, emit `training_compliance_contract.md` from the live graph binding (digraph name, freshness column, binding marker, and other required tokens) — do not leave a one-shot static brief. Do not alter the seed DuckDB, model registry service, or seed policy/binding files.

The verifier may rewrite policy and graph-binding files and invoke the CLI on alternate DuckDB training-run probes; emitted verdicts, findings, lineage, and contract tokens must follow those live ML governance inputs.
