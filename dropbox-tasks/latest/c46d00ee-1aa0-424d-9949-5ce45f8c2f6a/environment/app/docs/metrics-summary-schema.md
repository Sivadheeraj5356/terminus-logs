# Metrics summary schema

`/app/output/metrics-summary.json` is compact JSON on one line followed by a single trailing newline.

Keys in insertion order:
- policy_kind
- record_count
- unique_services
- total_latency_ms
- max_latency_ms
- min_latency_ms
- source_sha256

Rules:
- policy_kind comes from metadata-policy.json policyKind and must match exactly.
- metrics-cli validates policyKind on every invocation, including --input/--out runs that only write the report (not only when writing metrics-summary.json), and exits non-zero when policyKind differs from metadata-release.
- record_count is the number of normalized metric records written.
- unique_services is the count of distinct service names after sorting and deduplication.
- total_latency_ms sums latency_ms across all records.
- max_latency_ms and min_latency_ms are the maximum and minimum latency_ms values across records.
- source_sha256 is lowercase hex SHA256 of the raw fixture input bytes.
