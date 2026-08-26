# With manifest parsing and catalog connectivity in place, finish the lock pipelin

- **UUID:** `7ec1ef7a-7aa1-4b24-bb20-65a14b190356`
- **Slug:** `with-manifest-parsing-and-catalog-connectivity-in-place-fini`
- **Category:** build-and-dependency-management
- **Difficulty:** medium

## Summary

With manifest parsing and catalog connectivity in place, finish the lock pipeline. Join the approval and platform constraint tables, resolve versions from the catalog, and emit a deterministic lock file that passes schema validation.

Requirements: - Implement `HelixPipeline.Catalog.Queries.fetch_enriched/4` to join `dependency_approvals` with `platform_constraints` for the requested package names and platform (`os`, `arch`). Omit packages with no approval row.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
