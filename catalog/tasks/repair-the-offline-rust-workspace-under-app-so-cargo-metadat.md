# Repair the offline Rust workspace under /app so cargo metadata succeeds without 

Submission: `c46d00ee-1aa0-424d-9949-5ce45f8c2f6a`  
Slug: `repair-the-offline-rust-workspace-under-app-so-cargo-metadat`  
Latest archive: `c46d00ee-1aa0-424d-9949-5ce45f8c2f6a_submission_2026-07-18T05_32_04.241Z.zip`  
Revisions: 3

## Task summary

Repair the offline Rust workspace under /app so cargo metadata succeeds without network access and /app/scripts/build-release.sh completes successfully. Preserve the public RecordMetric derive exposed by metrics-core and keep the release reproducible from the supplied lock, policy, vendor archive, and fixtures. After release, /app/output must contain exactly dep-graph.json, metrics-report.json, and metrics-summary.json. /app/dist must contain metadata-manifest.json, audit-trail.ndjson, vendor-lock.sha256, and checksums.sha256. The graph and audit CLIs must validate their configured inputs, the metrics tools must produce deterministic rollups, and every artifact must follow its documented schema, ordering, path, and failure behavior.

Required artifacts include: `/app/scripts/build-release.sh`, `/app/output`, `/app/dist`, `/app/docs/metadata-contract.md`, `/app/docs/manifest-schema.md`, `/app/docs/dep-graph.md`, `/app/docs/metrics-summary-schema.md`, `/app/fixtures`.

Author anonymous tagged this **hard** build-and-dependency-management task (cargo, metadata, offline-build, rust, metrics).

Time estimates: expert ~290 min, junior ~580 min.

Harbor timeouts: agent 1500.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `c46d00ee-1aa0-424d-9949-5ce45f8c2f6a_submission_2026-07-18T05_32_04.241Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
