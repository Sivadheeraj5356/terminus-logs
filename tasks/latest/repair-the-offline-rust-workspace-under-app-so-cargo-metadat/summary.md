# Repair the offline Rust workspace under /app so cargo metadata succeeds without

- **UUID:** `c46d00ee-1aa0-424d-9949-5ce45f8c2f6a`
- **Slug:** `repair-the-offline-rust-workspace-under-app-so-cargo-metadat`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Repair the offline Rust workspace under /app so cargo metadata succeeds without network access and /app/scripts/build-release.sh completes successfully. Preserve the public RecordMetric derive exposed by metrics-core and keep the release reproducible from the supplied lock, policy, vendor archive, and fixtures.

After release, /app/output must contain exactly dep-graph.json, metrics-report.json, and metrics-summary.json. /app/dist must contain metadata-manifest.json, audit-trail.ndjson, vendor-lock.sha256, and checksums.sha256.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
