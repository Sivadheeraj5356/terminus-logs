# # Beat Every Room in Glyph Mill

- **UUID:** `0703f1cf-1690-4142-a968-808841968442`
- **Slug:** `beat-every-room-in-glyph-mill`
- **Category:** games
- **Difficulty:** hard

## Summary

Glyph Mill is an old terminal game sitting at `/app/glyph-mill`. Each room is a grid you walk one cell at a time by feeding it a sequence of glyphs, and you win a room by landing on its target after an exact number of moves, while also passing through any beacon cells it demands along the way (a beacon at move index N means you must be standing on that cell after exactly N moves, index 0 being the start cell before any move has been made).

Nobody kept notes on how the game works, though — which YAML/TOML rule pack a room actually draws from (part of that pick happens inside the compiled game, not something you can read off a hint file or a directory listing) or how feeding it a glyph moves you on the grid. Win every room.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
