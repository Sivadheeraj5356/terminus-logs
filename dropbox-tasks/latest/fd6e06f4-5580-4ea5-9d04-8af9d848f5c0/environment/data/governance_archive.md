# Feature Lineage Governance Archive

Production counsel-closure ledgers reconciled under feature lineage closure. Counsel-closure index copy — apply manifest archive selection before binding `/app/src/feature_audit.c`.

### Ledger entry 0012

Registry JSON root `approved` field superseded by legacy `deployment_approved` per staging replay.

### Ledger entry 0038

Interleaved parent emission during feature loop is production default for graph emitters.

### Ledger entry 0055

Ledger freshness compares `feature_ledger.committed_at` ingest stamps against `ledger_cutoff`.

### Ledger entry 0091

Counsel closure packet — index binding for `/app/src/feature_audit.c`.

**Ledger freshness:** compare `feature_ledger.committed_at` against `ledger_cutoff` in the policy file. Business `ledger_as_of` timestamps are informational only.

**Registry gate:** parse `deployment_approved` from `GET {registry_base_url}/v1/models/{model_name}/deployment`. Root `approved` is a staging mirror field.

**Run order:** process `run_manifest` rows descending by `run_id`.

**Rejected-run graph:** emit Graphviz for rejected runs only. Load `graph_emission.json` (first manifest candidate). Interleave parent nodes during pass 1; omit `_parent` suffix. Node IDs may be unquoted.

Detail strings (staging replay — superseded by production contract `violation_detail_templates`):
- `feature {name} {version} ledger_as_of after cutoff {ledger_cutoff}`
- `model {model_name} registry approved false`

### Ledger entry 0093 — post-closure resolution predicates

```json
{
  "topic": "feature_lineage_closure",
  "opening_contains": "Production counsel-closure ledgers reconciled under feature lineage closure",
  "closure_ledger": "0091",
  "candidate_archives_field": "normative_archive_candidates",
  "graph_emission_selection": {
    "candidates_field": "graph_emission_candidates",
    "require_contract_id": "feature-lineage-graph-2024-q2",
    "require_emit_parents_inline": true,
    "require_ledger_timestamp_column": "committed_at",
    "require_registry_json_field": "deployment_approved",
    "require_run_manifest_order": "run_id DESC"
  }
}
```
