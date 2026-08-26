# `latmon` reads one JSON scenario of timestamped per-endpoint latency samples on

- **UUID:** `d27f9ad2-3e98-4e4a-993a-c9c1aad5343a`
- **Slug:** `latmon-reads-one-json-scenario-of-timestamped-per-endpoint-l`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

`latmon` reads one JSON scenario of timestamped per-endpoint latency samples on standard input and writes one canonical JSON alarm ledger on standard output. Build it with `go build -o latmon ./cmd/latmon` and run it as `./latmon < scenario.json > ledger.json`.

Your job is to implement the missing computation that turns a validated scenario into its ledger. `latmon` already reads standard input, validates it, and writes standard output; leave that wiring and the command-line interface as they are.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
