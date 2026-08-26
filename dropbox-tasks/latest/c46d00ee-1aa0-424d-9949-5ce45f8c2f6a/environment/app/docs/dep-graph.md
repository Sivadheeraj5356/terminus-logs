# Dependency graph contract

## Acyclic workspace

`cargo metadata --offline` must succeed against /app. The public metrics API exposes the RecordMetric derive from metrics-macros through metrics-core. The workspace must not form a cargo dependency cycle that prevents metadata resolution, and the derive must remain part of the public metrics-core surface.

## dep-graph.json

metacycle graph writes /app/output/dep-graph.json. The `nodes` array is an allowlist filtered by /app/config/graph-lock.csv: only packages named in that lock file appear, each with the version reported by cargo metadata. Nodes are sorted by `id` ascending. `edgeCount` counts resolve-graph edges whose both endpoints appear in the allowlist.

Compact JSON, UTF-8, single trailing newline. Top-level keys in insertion order: edgeCount, nodes. Each node keys in insertion order: id, version.
