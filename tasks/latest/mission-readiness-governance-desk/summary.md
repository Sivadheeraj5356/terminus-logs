# # Mission readiness governance desk

- **UUID:** `9b8419bb-5b2a-493c-acfd-ab51f7d02b23`
- **Slug:** `mission-readiness-governance-desk`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Fix the source under /app/environment so the Mission Readiness Review Board command regenerates a consistent determination from a supplied record directory. Build and run /app/bin/boardctl review with a record directory, policy JSON, output directory, and persistent state file; an optional clear-state switch empties prior state before the review.

The verifier uses /app/environment/data/policy_standard.json, bundled orbital records, and generated records that change evidence order, policy floors, shared state, repeated reviews of the same case, overdue commitments, and invalid authority declarations. Go and Rust toolchains are installed in the image.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
