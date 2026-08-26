# The shipped Go equivalence service audits twenty cross compilation build session

- **UUID:** `887c1838-7921-488f-9548-370711c061ef`
- **Slug:** `the-shipped-go-equivalence-service-audits-twenty-cross-compi`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The shipped Go equivalence service audits twenty cross compilation build sessions under /app/build-sessions named build_01.json through build_20.json. Each session records toolchain artifacts, compilation checkpoints, ordered stage events, rollback attempts, distributed shard merges, and optimization pass fingerprints.

Implement EvaluateSession in /app/equivalence-engine/evaluate.go without changing toolchain-cli/main.go or report-writer/emit.go. Run make build from /app until /app/bin/artifact-equivalence-checker exceeds 2048 bytes.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
