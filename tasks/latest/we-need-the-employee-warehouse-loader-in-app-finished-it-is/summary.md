# We need the employee warehouse loader in /app finished. It is a Rust CLI that sh

- **UUID:** `04c4a6cd-c487-4e44-9a73-8705c0c26727`
- **Slug:** `we-need-the-employee-warehouse-loader-in-app-finished-it-is`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

We need the employee warehouse loader in /app finished. It is a Rust CLI that should be run as cargo run -- ingest --db /absolute/path/to/warehouse.sqlite --input /absolute/path/to/feed.csv, and the input can also be a directory of csv files.

The feed contract and the SQLite table contract are in /app/docs/source_contract.txt. The business requirement is full Slowly Changing Dimension Type 2 tracking for the employee roster.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
