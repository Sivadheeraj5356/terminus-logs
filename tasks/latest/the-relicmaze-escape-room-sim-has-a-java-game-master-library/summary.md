# The RelicMaze escape-room sim has a Java game-master library under /app/relicmaz

- **UUID:** `873bceac-14b3-4139-b8a8-623a18e27bf3`
- **Slug:** `the-relicmaze-escape-room-sim-has-a-java-game-master-library`
- **Category:** games
- **Difficulty:** hard

## Summary

The RelicMaze escape-room sim has a Java game-master library under /app/relicmaze, and right now `com.relicmaze.Resolver` is just a stub. I need it to actually answer seekers: given a capsule and a player's transcript, `resolve()` has to replay the transcript and return the exact narration and the ordered list of next actions that a Keeper would speak.

The canonical rules for all of that live in /app/relicmaze/manual/keeper-manual.md, which is the source of truth for how every line of the account is composed. The room, relic, and passage data is not in any file you can read directly; it lives in the running PostgreSQL database (see /app/relicmaze/db.properties for the connection).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
