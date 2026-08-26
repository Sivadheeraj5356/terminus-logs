# This task asks for the exact perft node count of a Chess960 (Fischer Random

- **UUID:** `0ce31b81-1432-4620-b06e-2014f3f2575a`
- **Slug:** `this-task-asks-for-the-exact-perft-node-count-of-a-chess960`
- **Category:** games
- **Difficulty:** hard

## Summary

This task asks for the exact perft node count of a Chess960 (Fischer Random Chess) position, where the castling rule's king/rook overlap cases are the central difficulty. A perft count at a given depth is the total number of leaf positions reachable by exactly that many consecutive plies of strictly legal play from a starting position, with every side to move choosing among all of its own legal moves at every ply.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
