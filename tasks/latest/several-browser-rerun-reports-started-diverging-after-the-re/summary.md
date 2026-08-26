# Several browser rerun reports started diverging after the retry-policy cleanup.

- **UUID:** `21db18f7-045f-42d8-8f80-7fe70f2def24`
- **Slug:** `several-browser-rerun-reports-started-diverging-after-the-re`
- **Category:** debugging
- **Difficulty:** hard

## Summary

Several browser rerun reports started diverging after the retry-policy cleanup. Historical flaky-test prioritization has been miscounting failures since the v2.0 schema changes introduced rerun session tracking and soft-deleted rows in the SQLite history database.

Before expanding the reproduction tooling further, stabilize historical aggregation so flaky counts reflect only valid original sessions. The flaky-repro CLI under /app reads from /app/db/history.db; see /app/README.md for schema context and /app/docs/output-contracts.md for the report.json layout.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
