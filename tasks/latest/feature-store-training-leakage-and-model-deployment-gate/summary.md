# # Feature Store Training Leakage and Model Deployment Gate

- **UUID:** `fd6e06f4-5580-4ea5-9d04-8af9d848f5c0`
- **Slug:** `feature-store-training-leakage-and-model-deployment-gate`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Certify each ML model training run stored in `/app/data/lineage.duckdb` before deployment: Repair `/app/src/feature_audit.c` so the training-compliance evaluator writes correct ML governance artifacts under `/app/output/`. Policy cutoffs, registry base URL, freshness column, violation detail templates, lineage digraph layout, and contract tokens are supplied by the live inputs under `/app/data/` (including `governance_policy.json`, the graph emission binding selected for this feature-store domain, and `contract_binding_requirements.json`).

Key requirements: **Feature leakage** — reject training runs that bind features whose store availability timestamp is after the training ledger cutoff (temporal leakage into the training window).; **Model registry gate** — reject training runs whose model artifact fails the live model-deployment registry check.; **Feature lineage** — for rejected runs, emit a Graphviz feature-lineage diagram of the training feature graph..

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
