# This is a Rust scientific simulation workspace under `/app/environment`. The sui

- **UUID:** `73111334-1c5d-482c-9281-a9e221708c19`
- **Slug:** `this-is-a-rust-scientific-simulation-workspace-under-app-env`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

This is a Rust scientific simulation workspace under `/app/environment`. The suite models fog-of-war visibility replay over a rectangular cell grid, cadence-gated fade of stale coverage, ally observer pooling with resident-memory accounting, and a certified session ledger.

The shipped build compiles and emits `/app/output/session_ledger.json`, but the ledger does not yet satisfy the full protocol contract. Plausible legacy code paths may still alias planes, use inclusive phase boundaries, or mis-scope checksums; the public contract is authoritative.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
