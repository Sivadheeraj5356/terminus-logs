# Repair the offline Go module policy-lock sources under /app so resolution stays

- **UUID:** `71fe619a-7cfa-437a-99d4-5c62cd96be62`
- **Slug:** `repair-the-offline-go-module-policy-lock-sources-under-app-s`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Repair the offline Go module policy-lock sources under /app so resolution stays consistent for clean copied roots, the offline mirror at /app/var/module-mirror/, workspace overlays, platform targets (GOOS/GOARCH), and interrupted policy-index updates. In-tree smoke runs can look fine.

Copied roots, cross-platform runs, directive conflicts, legacy lock migrations, and resumed policy-db refresh runs show mismatched lockfiles, policy reports, or stale pin decisions. Rebuild with the workflow in /app/docs/BUILD.md; hand-written final artifacts are insufficient.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
