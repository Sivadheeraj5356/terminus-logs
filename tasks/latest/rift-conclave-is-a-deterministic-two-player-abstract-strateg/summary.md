# Rift Conclave is a deterministic two-player abstract strategy game. For each tou

- **UUID:** `50a665fe-73d8-43bb-bce1-9705b69a2f74`
- **Slug:** `rift-conclave-is-a-deterministic-two-player-abstract-strateg`
- **Category:** games
- **Difficulty:** medium

## Summary

Rift Conclave is a deterministic two-player abstract strategy game. For each tournament position, the league needs the exact guaranteed score and principal variation under perfect player and rival play.

Use the official game rules in `/app/task_file/arena_rules.md`; positions vary in their boards, hands, omen sets, round horizons, and resources. Complete the Go match analyst beginning at `/app/task_file/main.go` and build `/app/task_file/conclave` from the Go package in `/app/task_file`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
