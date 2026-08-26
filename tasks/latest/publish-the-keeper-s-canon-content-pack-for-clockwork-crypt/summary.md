# Publish the Keeper's Canon content pack for Clockwork Crypt, a Lua terminal puzz

- **UUID:** `a96d5a8b-488c-4392-9b00-c60a8895b5cf`
- **Slug:** `publish-the-keeper-s-canon-content-pack-for-clockwork-crypt`
- **Category:** games
- **Difficulty:** hard

## Summary

Publish the Keeper's Canon content pack for Clockwork Crypt, a Lua terminal puzzle adventure under `/app`. This is a game-content reconstruction challenge: use the designers' long-form lore journal to determine the adopted map, props, locks, character encounters, clue-card art, and staged twelve-beat finale.

The finished adventure must let a player traverse the intended route, complete the adopted item-and-lock chain, meet every character in the intended state, perform the finale in order, and view the nine clue cards in their canonical atlas arrangement. `/app/docs/keeper_journal.md` is the authoritative game-design record; its closing construction identifies which earlier evidence leaves supply the adopted values, inherited identities, performance tuples, and art recipe.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
