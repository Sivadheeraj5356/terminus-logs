# gosaw works a sawmill and, for each batch of rods handed to it, says who is winn

- **UUID:** `cb84d31f-de2f-4367-bbef-14b2bb8a827b`
- **Slug:** `gosaw-works-a-sawmill-and-for-each-batch-of-rods-handed-to-i`
- **Category:** games
- **Difficulty:** hard

## Summary

gosaw works a sawmill and, for each batch of rods handed to it, says who is winning. A rod is a whole number of units of timber long.

A turn is one cut: a player takes a single rod and saws it across into two rods, each one unit or more. The two players take turns, and the player who makes the last cut wins, so the player faced with a row too short to saw has lost.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
