# Hey — the SVOD residual rollups under `/app/output/` are wrong and incomplete af

- **UUID:** `4a631aa6-d9ba-47b2-9fcf-a0481acce205`
- **Slug:** `hey-the-svod-residual-rollups-under-app-output-are-wrong-and`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Hey — the SVOD residual rollups under `/app/output/` are wrong and incomplete after we merged the new usage shards. Build the Go processor under `/app` so `go run ./cmd/residual` reads every JSONL shard under `/app/data/usage`, the catalog CSVs under `/app/data/`, and config under `/app/config/`, leaves all inputs byte-identical, and writes `/app/output/residual_daily.csv`, `/app/output/residual_weekly.csv`, and `/app/output/escrow_ledger.jsonl`.

Use only the Go standard library (`GOPROXY=off`). Do not hardcode rollup results for the bundled feeds alone.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
