# The offline dependency resolver in /app is used by prism prism release workers t

- **UUID:** `df041e50-c298-4587-a3fe-75bea002b266`
- **Slug:** `the-offline-dependency-resolver-in-app-is-used-by-prism-pris`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The offline dependency resolver in /app is used by prism prism release workers to update a deterministic dependency forge lockfile from a workspace request file and an on-disk package registry. Repair the prism-dependency-forge CLI so it follows /app/docs/resolver-contract.md.

It must resolve aliases, version constraints, yanked releases, transitive dependencies, and feature-driven dependencies without using the network. Successful runs write the deterministic dependency forge lockfile schema described in /app/docs/lock-schema.md; failed runs write a conflict report and must not modify any existing lockfile.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
