# # Selene lunar survival board-game planner

- **UUID:** `0ab515ca-056e-4b9d-8279-6dbe5bf55577`
- **Slug:** `selene-lunar-survival-board-game-planner`
- **Category:** games
- **Difficulty:** hard

## Summary

Write the player bot for Selene, a deterministic turn-based lunar colony survival board game. Each sol is one game turn: choose the crew's ration policy and colony action, resolve the published hazard for that turn, satisfy the end-of-campaign charter, and emit the winning game replay with its resource ledger.

The required Go entry point is `/workspace/task_file/main.go`. It is run from `/workspace` with:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
