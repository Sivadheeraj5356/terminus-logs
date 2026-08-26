# Layout

/app/registry holds the package registry, one directory per package, one subdirectory per released version, each with index.json and a Go source stub (plus a MIGRATION.md where a version changed its public surface). /app/manifest.toml lists the root requirements. /app/RULES.md is the resolution and build contract. /app/docs/registry-format.md walks through the index.json shape using packages that are not part of this registry. /app/project holds the fixed consumer.go and its go.mod.
