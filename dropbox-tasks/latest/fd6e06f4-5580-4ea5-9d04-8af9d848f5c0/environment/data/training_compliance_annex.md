## Sealed training-compliance annex

Normative ML feature-store training-run gate. Resolve freshness, registry field, run order, digraph layout, detail templates, and emission order from the manifest-selected archive (ledger **0091**) and the ledger **0093**-selected graph emission contract under `/app/data/` — including nested production envelopes when present.

### DuckDB tables

- `feature_ledger(feature_name, feature_version, ledger_as_of, committed_at, source_table)`
- `run_manifest(run_id, model_name, scenario)`
- `run_features(run_id, feature_name, feature_version)`
- `lineage_edges(child_feature, parent_feature)`

### Outputs

Emit `/app/output/training_run_verdicts.json`, `leakage_findings.csv`, `rejected_run_lineage.dot`, and `training_compliance_contract.md`.

Schemas, key orders, violation literals/templates, Graphviz digraph/rankdir/pass-1/pass-2 rules, and freshness column names bind through the selected graph emission contract's production envelope (not envelope-root decoys or scratch copies).

Freshness joins `run_features` to `feature_ledger` on both `feature_name` and `feature_version`. Compare the production freshness column to policy `ledger_cutoff` with strict `>`. Pipeline ingest column `committed_at` is informational only.

### Contract brief

Open `/app/data/contract_binding_requirements.json` and include every required token it names (filenames, ledgers, violation literals, live freshness column / digraph from the production graph binding, and the manifest `binding_marker`) as verbatim substrings. State that `committed_at` is informational only. Re-emit the brief on every evaluate so live graph-binding mutations are reflected.
