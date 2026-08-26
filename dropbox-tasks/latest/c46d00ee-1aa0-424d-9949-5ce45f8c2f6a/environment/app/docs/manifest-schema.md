# metadata-manifest.json schema

Compact JSON, UTF-8, trailing newline. Serialized output must preserve the exact key insertion order listed below — not merely include the required fields. The top-level object, metadataPolicy object, and each dependencies element must emit keys in this order when written to disk.

Top-level keys in insertion order: metadataEpoch, toolVersion, vendorRoot, metadataPolicy, lockDigest, moduleGraphHash, graphOrder, dependencies.

metadataPolicy keys in insertion order: offlineLocked, vendorRoot.

graphOrder is an array of dep values from config/graph-order.csv sorted by order ascending. The audit CLI loads that file via `--order`.

dependencies is an array sorted ascending by dep. Each element keys in insertion order: dep, version, role, kind. Each version is the Cargo.lock version string for that crate (workspace and registry crates alike).

lockDigest is lowercase hex SHA256 of the raw bytes of config/graph-lock.csv.

## moduleGraphHash

Lowercase hex SHA-256 of newline-joined `dep|version` lines built from the **manifest dependencies array** (the same version strings written into that array). Sort those full lines as opaque strings ascending — not by dep name alone — then join with `\n` and hash. Include every dependency entry (workspace and registry). Do not re-strip versions for the hash beyond what already appears in the array.

Worked example with two entries `{dep: serde, version: 1.0.228}` and `{dep: serde_json, version: 1.0.138}`:

1. Form lines `serde|1.0.228` and `serde_json|1.0.138`.
2. Full-string sort places `serde_json|1.0.138` before `serde|1.0.228` because `|` (0x7C) sorts after `_` (0x5F).
3. Hash the UTF-8 bytes of `serde_json|1.0.138\nserde|1.0.228`.

# dep-graph.json schema

Compact JSON, UTF-8, trailing newline. Serialized output must preserve the exact key insertion order listed below.

Top-level keys in insertion order: edgeCount, nodes.

nodes lists only packages named in config/graph-lock.csv. Each node uses versions from cargo metadata. nodes is sorted by id ascending. Each node keys in insertion order: id, version.

edgeCount counts resolve-graph dependency edges where both endpoints appear in graph-lock.csv.

# audit-trail.ndjson schema

One compact JSON object per line, LF endings, single trailing newline on the file. Each line keys in insertion order: dep, kind, matched, role, version. Lines sorted by dep ascending. matched is true when the lock version matches Cargo.lock with patch suffix ignored.

# metrics-report.json schema

Compact JSON, UTF-8, trailing newline. Keys in insertion order: services, serviceTotals, recordCount, totalLatencyMs.

services is sorted ascending unique service names. serviceTotals maps each service to the sum of latency_ms for that service with keys sorted ascending.

# metrics-summary.json schema

Compact JSON, UTF-8, trailing newline. Keys in insertion order: policy_kind, record_count, unique_services, total_latency_ms, max_latency_ms, min_latency_ms, source_sha256.

policy_kind must equal metadata-policy.json policyKind. metrics-cli validates policyKind on every invocation (including plain --input/--out report runs) and exits non-zero when it differs from metadata-release.
