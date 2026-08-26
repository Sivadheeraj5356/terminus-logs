# giri is our engine for a capture-and-territory board game played on an arbitrary

- **UUID:** `0435f10d-6622-40c5-af14-cbf3d0aa9690`
- **Slug:** `giri-is-our-engine-for-a-capture-and-territory-board-game-pl`
- **Category:** games
- **Difficulty:** hard

## Summary

giri is our engine for a capture-and-territory board game played on an arbitrary graph board, and the rules core still needs to be written. The board's intersections and their adjacencies are in /app/board.spec, and the recorded games are the move logs under /app/games.

The rules — groups and liberties, how captures resolve, when a move is suicide, the repetition rule, passing and how a game ends, and area scoring — are written up in /app/docs/RULES.md; the move-log grammar is in /app/docs/NOTATION.md; the results schema, the group-graph format, and the command-line interface are in /app/docs/STORE.md. The Rust crate under /app already has the command-line entry point and the notation parser; the board model, the capture and legality logic, the repetition check, scoring, the results store, and the graph output are stubbed out.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
