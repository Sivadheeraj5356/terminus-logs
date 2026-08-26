# metrics offline metadata factory

Repair the workspace so `/app/scripts/build-release.sh` succeeds without network access and `cargo metadata` can resolve the complete workspace. Preserve the public `RecordMetric` derive exposed by `metrics-core`.

The release must produce exactly `dep-graph.json`, `metrics-report.json`, and `metrics-summary.json` under `/app/output`. It must also produce `metadata-manifest.json`, `audit-trail.ndjson`, `vendor-lock.sha256`, and `checksums.sha256` under `/app/dist`.

See `/app/docs/metadata-contract.md` and the sibling schema documents for the artifact layouts, CLI behavior, validation rules, and deterministic ordering requirements.
