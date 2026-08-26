# # Game balance archaeology

- **UUID:** `bac889e0-9c8d-413d-8916-6c4bd405a5a5`
- **Slug:** `game-balance-archaeology`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The live-ops desk archived years of competitive telemetry through a Go pipeline under `/app/environment`, but exports no longer line up with design reviews. Era windows look calendar-driven, actor rates disagree with match volumes, and the stamped archive seal fails audit replay.

Repair sources under `/app/environment`, rebuild with `make -C /app/environment all`, and regenerate `/app/output/balance_archive.json` through `/opt/simbin/balancectl` per `/app/environment/docs/cli_invocation.txt`. Binding formulas live in `/app/environment/docs/balance_contract.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
