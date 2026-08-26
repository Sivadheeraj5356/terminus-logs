# ML Feature Store Lineage Governance Archive

Production counsel-closure ledgers reconciled under ML feature-store training-run closure. This archive governs feature leakage detection, model-deployment registry gates, and lineage graph emission for rejected model training runs. Ignore staging replays, lab graph emitters, and pre-closure index copies elsewhere under `/app/data/`.

### Ledger entry 0012

Workshop replay: registry JSON carried legacy `deployment_approved` alongside root `approved`.

### Ledger entry 0038

Staging graph emitter interleaved parent nodes during the feature loop (superseded).

### Ledger entry 0055

Lab replay compared `committed_at` ingest stamps against policy cutoff (superseded for audit).

### Ledger entry 0091

Counsel closure packet — production binding for `/app/src/feature_audit.c`.

Resolve evaluator semantics from the ledger **0093**-selected graph emission contract's root-level nested `production_binding` (not envelope-root sibling fields, not `counsel_scratch` copies, not lab/staging archives).

**Ledger freshness:** join `run_features` to `feature_ledger` on matching `feature_name` **and** `feature_version`. Compare the production binding's freshness timestamp column against policy `ledger_cutoff` with a strict greater-than predicate (`>`, not `>=`). Pipeline ingest metadata columns that the binding does not select remain informational only.

**Registry gate:** `GET {registry_base_url}/v1/models/{model_name}/deployment` — parse the boolean named by the production binding's registry JSON field. Ignore other booleans on the same response.

**Run order:** process `run_manifest` rows using the production binding's `run_manifest_order`.

**Violation taxonomy:** Emit only these exact `violation_type` string literals in `training_run_verdicts.json`, `leakage_findings.csv`, and graph `xlabel` tokens — do not rename or paraphrase:

| Literal | When |
|---------|------|
| `leaking_feature` | A selected feature's matched freshness timestamp exceeds `ledger_cutoff` |
| `unapproved_model` | Registry deployment gate fails for the run's `model_name` |

Forbidden synonyms include `feature_leakage`, `registry_unapproved`, `post_cutoff_feature`, or other invented labels.

**Violation emission order:** within each run (JSON `violations` and CSV rows), emit every `leaking_feature` first sorted by `feature_name ASC` then `feature_version ASC`, then `unapproved_model` last. Lab emitters that reverse registry-before-leakage are superseded.

**Output object shapes:** `training_run_verdicts.json` and `leakage_findings.csv` must use exactly the key/column lists in the ledger **0093**-selected graph emission contract (`verdict_json_schema`, `findings_csv_columns`) — forbid additional properties/columns.

**Rejected-run graph:** emit Graphviz for rejected runs only. Resolve graph emission body from manifest `graph_emission_candidates` using ledger **0093** `graph_emission_selection` predicates. Digraph name, rankdir, pass-1 feature order, pass-2 parent suffix, edge direction, and detail templates bind exclusively through root `production_binding` on that selected contract. Node identifiers must be double-quoted. Each node ID is declared **exactly once** — combine `shape`, `label`, and optional `xlabel` in a single bracketed declaration in attribute order `shape`, `label`, `xlabel`; never re-declare the same node ID to add attributes later. Use two passes per subgraph:

1. **Run + selected features:** emit `{run_id}_run` with `shape=box` and label from production `pass1_run_node_label` (never the literal word `run`), then each `run_features` row ordered by production `pass1_feature_order_by` as `{run_id}_{feature_name}` with `shape=ellipse` and `label="{feature_name}"` (bare name only — **no** `@version` suffix), emitting the run→feature edge immediately after each feature node.
2. **Direct lineage parents (after pass 1 completes):** for each direct `lineage_edges` row joined to the run's features, ordered by `child_feature`, `parent_feature`, emit the parent reference node `{run_id}_{parent_feature}{pass2_parent_suffix}` with `shape=box` and `label="{parent_feature}"`, then the **child→parent** edge per production `pass2_edge_template` / `pass2_edge_direction` (never the superseded parent→child lab direction).

Pass-2 parent nodes are box-shaped reference nodes using the production binding's `pass2_parent_suffix`; they are not the same as pass-1 feature ellipses. Ledger 0038's interleaved parent emission during the feature loop is superseded.

**Formatting:** digraph body lines use 2 leading spaces; lines inside each `subgraph cluster_{run_id}` use 4 leading spaces.

Annotate leaking features and unapproved runs with `xlabel="VIOLATION: {violation_type}"` on the violating node. Direct parents only — no transitive closure.

Detail strings bind through production `violation_detail_templates` (not graph node labels, not envelope-root or scratch templates).

### Ledger entry 0092

Post-audit note: deterministic reruns must reproduce byte-identical outputs.

### Ledger entry 0093 — post-closure resolution predicates

```json
{
  "topic": "feature_lineage_closure",
  "opening_contains": "Production counsel-closure ledgers reconciled under ML feature-store training-run closure",
  "closure_ledger": "0091",
  "candidate_archives_field": "normative_archive_candidates",
  "graph_emission_selection": {
    "candidates_field": "graph_emission_candidates",
    "prefer_production_binding": true,
    "require_nested_production_binding": true,
    "require_contract_id": "feature-lineage-graph-2024-q2",
    "require_two_pass_emission": true,
    "reject_emit_parents_inline": true,
    "require_quote_node_ids": true,
    "require_forbid_version_in_node_label": true,
    "require_pass2_edge_direction": "child_to_parent",
    "require_forbid_additional_verdict_properties": true,
    "require_single_node_declaration": true,
    "violation_type_literals": ["leaking_feature", "unapproved_model"],
    "require_violation_emission_order": ["leaking_feature", "unapproved_model"],
    "require_pass1_run_node_label": "{run_id}",
    "reject_registry_json_field": "deployment_approved",
    "reject_run_manifest_order": "run_id DESC",
    "reject_pass2_edge_direction": "parent_to_child",
    "reject_violation_emission_order": ["unapproved_model", "leaking_feature"],
    "reject_pass1_run_node_label": "run",
    "reject_ledger_timestamp_column": "committed_at",
    "reject_emit_parents_inline_true": true,
    "violation_detail_templates_field": "violation_detail_templates",
    "bind_fields_from_production_binding": [
      "digraph_name",
      "rankdir",
      "pass1_feature_order_by",
      "pass2_parent_suffix",
      "ledger_timestamp_column",
      "registry_json_field",
      "run_manifest_order",
      "violation_detail_templates"
    ]
  },
  "training_compliance_annex": "training_compliance_annex.md"
}
```
