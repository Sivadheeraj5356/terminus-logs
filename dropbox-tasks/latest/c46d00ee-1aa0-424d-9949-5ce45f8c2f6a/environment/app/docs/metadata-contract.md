# Offline metadata release contract

## Required artifacts

After a successful release pipeline under /app, these paths must exist with the shapes documented here and in the sibling schema documents:

| Path | Role |
|------|------|
| /app/output/dep-graph.json | Lock-filtered dependency graph (see dep-graph.md) |
| /app/output/metrics-report.json | Fixture rollup from metrics-cli |
| /app/output/metrics-summary.json | Sibling summary beside the report |
| /app/dist/metadata-manifest.json | Vendor attestation manifest |
| /app/dist/audit-trail.ndjson | Sidecar beside the manifest |
| /app/dist/vendor-lock.sha256 | Digest of vendor/serde/Cargo.toml |
| /app/dist/checksums.sha256 | Digests of every dist file except itself |

/app/output contains exactly dep-graph.json, metrics-report.json, and metrics-summary.json.

## Workspace and release behavior

Cargo metadata and release builds must succeed with network access disabled and the supplied lock and vendored source material. Release cargo build invocations must include both `--locked` and `--offline`, and the release environment must export `CARGO_NET_OFFLINE=true`. The resolved vendor root must match metadata-policy.json, and metadataPolicy.offlineLocked in the manifest is true. The workspace dependency graph must be acyclic while metrics-core continues to expose the public RecordMetric derive. Any edit that restores metadata is acceptable so long as the resolved package graph no longer contains a metrics-macros to metrics-core dependency edge.

## SOURCE_DATE_EPOCH

metadataEpoch in the manifest equals the sourceDateEpoch field from /app/config/metadata-policy.json. The release environment must export that value as `SOURCE_DATE_EPOCH` before cargo builds and artifact generation.

## metacycle graph and audit

metacycle graph consumes --lock config/graph-lock.csv.

metacycle audit consumes --lock config/graph-lock.csv, --order config/graph-order.csv, --policy config/metadata-policy.json, and --out pointing at the manifest path. graphOrder in the manifest is the dep column from graph-order.csv sorted by the order column ascending. Audit exits non-zero when a graph-lock.csv version does not match Cargo.lock after ignoring a patch suffix. It writes audit-trail.ndjson beside --out.

## metrics-cli

`--input PATH --out PATH --policy PATH` writes the report at PATH and metrics-summary.json in the same directory. policyKind from metadata-policy.json must equal metadata-release on every non-health invocation before either file is written. Invalid input or policy data must fail without leaving partial output.

## vendor-lock.sha256

One sha256sum-compatible line for the policy-selected serde manifest, using a lowercase digest, two spaces before its workspace-relative path, and one trailing newline.

## checksums.sha256

Each line is a lowercase digest, two spaces, then a path relative to dist. Include every file under dist except checksums.sha256 itself, sorted by relative path. Do not list output files.

## graph-lock.csv

Every lock row appears in metadata-manifest.json dependencies sorted by dep ascending. Manifest versions are Cargo.lock versions; when comparing to the CSV, ignore text after +.
