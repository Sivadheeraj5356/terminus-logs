# The distributed columnar compaction optimizer at /app ships columnarctl, a C++ C

- **UUID:** `e699b548-c7ff-4c75-82b8-4e29abc52528`
- **Slug:** `the-distributed-columnar-compaction-optimizer-at-app-ships-c`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The distributed columnar compaction optimizer at /app ships columnarctl, a C++ CLI that ingests CLFC binary fragment catalogs through a staging snapshot, exports merge plans across row-range overlaps, validates plans, and repairs broken orderings. The implementation does not match the published contracts.

Behavioral rules, catalog layout, merge plan JSON, scan cost accounting, replica policy, and the ingest snapshot contract live under /app/docs/COMPACTION_CONTRACT.md and the other documents it references. Rebuild with make -C /app before testing.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
