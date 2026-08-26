# # Poset Chomp: game value, Grundy value, and remoteness

- **UUID:** `88f91d1f-9208-42aa-9df6-3fb94b729603`
- **Slug:** `poset-chomp-game-value-grundy-value-and-remoteness`
- **Category:** games
- **Difficulty:** hard

## Summary

Chomp is played on the order ideals of a finite partially ordered set (poset). For one position you must report four exact quantities under the **normal poison-loss** convention: the game value, the number of winning first moves, the Sprague-Grundy value, and the remoteness (optimal game length).

Complete the C++ program in `src/` so that `make` builds `./chomp`; it reads one position from stdin and writes a single line `V C G R` to stdout. Elements are labelled `0 ..

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
