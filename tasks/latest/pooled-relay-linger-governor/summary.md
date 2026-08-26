# # Pooled relay linger governor

- **UUID:** `1f6fc6bf-8f01-4913-a4f6-de272f5a4102`
- **Slug:** `pooled-relay-linger-governor`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Operations is shipping the Rust edge relay coordinator under `/app/environment` for offline shard polling. Bundled smoke workloads finish, but larger profiles either abort with descriptor pressure or leave idle pooled sockets unreclaimed after mock shards close quiet connections.

Complete the coordinator by fixing Rust source under `/app/environment` so pooled transport reuse, linger governance, and export reconciliation match the contract. Library behavior in the workspace crates must match the contract, not only the CLI layer.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
