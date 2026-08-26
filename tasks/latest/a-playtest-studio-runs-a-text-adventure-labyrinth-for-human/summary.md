# A playtest studio runs a text-adventure labyrinth for human testers and

- **UUID:** `fa8fdbaa-2060-4ac2-b51a-7da30a872339`
- **Slug:** `a-playtest-studio-runs-a-text-adventure-labyrinth-for-human`
- **Category:** games
- **Difficulty:** hard

## Summary

A playtest studio runs a text-adventure labyrinth for human testers and needs a hint oracle that lists every valid next action for a live session state. Sessions track room, inventory, consumed targets, and failed attempts.

World geography lives in plain JSON files. Forbidden actions are embedded as @RULE lines inside each world's game-master chronicle.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
