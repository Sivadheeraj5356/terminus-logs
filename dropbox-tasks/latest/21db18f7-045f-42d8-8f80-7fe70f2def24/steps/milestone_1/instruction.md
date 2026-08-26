Several browser rerun reports started diverging after the retry-policy cleanup. Historical flaky-test prioritization has been miscounting failures since the v2.0 schema changes introduced rerun session tracking and soft-deleted rows in the SQLite history database.

Before expanding the reproduction tooling further, stabilize historical aggregation so flaky counts reflect only valid original sessions. The flaky-repro CLI under /app reads from /app/db/history.db; see /app/README.md for schema context and /app/docs/output-contracts.md for the report.json layout.

Once fixed, node cli.js report should write /app/logs/report.json where only spec+browser pairs with both genuine failures and passes appear, total_flaky_combos matches the corrected dataset, and top_flaky is sorted by fail_count descending with spec_file ascending as the tie-break when fail counts match. Additional report field layout is in /app/docs/output-contracts.md.
