# # Claim ingestion normalizer

- **UUID:** `e09c287a-5fea-4161-a6b8-5512dd09ed62`
- **Slug:** `claim-ingestion-normalizer`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Please finish the Go CLI in `/workspace` for this first step. The command I need is: `go run /workspace/cmd/claimtower ingest --claims-root <dir> --as-of YYYY-MM-DD --claims-out <json> --issues-out <tsv>`

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
