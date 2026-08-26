# Snapshot contract

Path: /app/state/assay-snapshot.json

Required top-level fields:

- schema_version: 1
- ingest_seq: integer
- assay_bind: hex sha256 string
- config_canon_sha: hex sha256 of canonical config binding material
- coins: array of per-coin evaluation records produced at analyze time

Each coin record must include coin_id, status, mixing_rule, enrichment_model_id, density_band summary, xrf_bound summary (or null), feasible_region (or null), and reason when status is insufficient_data or inconsistent.

Export must read only this snapshot (plus ledger verification) and must not reload /app/data/.
