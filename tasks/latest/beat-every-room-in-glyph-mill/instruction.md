# Beat Every Room in Glyph Mill

Glyph Mill is an old terminal game sitting at `/app/glyph-mill`. Each room is
a grid you walk one cell at a time by feeding it a sequence of glyphs, and
you win a room by landing on its target after an exact number of moves,
while also passing through any beacon cells it demands along the way (a
beacon at move index N means you must be standing on that cell after
exactly N moves, index 0 being the start cell before any move has been
made). Nobody kept notes on how the game works, though — which YAML/TOML
rule pack a room actually draws from (part of that pick happens inside the
compiled game, not something you can read off a hint file or a directory
listing) or how feeding it a glyph moves you on the grid.

Win every room. Deliver your playbook as `/app/recovered/glyph_tool.py`
with three subcommands, each writing JSON to `--out <path>` for a given
`--root <dir>`: `discover` (for each room, its LMDB hint plus exactly which
rule files the game really reads for it, caught in the act rather than
guessed from the layout), `normalize` (fold everything `discover` found
into one flat rulebook), and `solve` (a winning move sequence per room,
using only that room's own glyphs, accepted by `glyph-mill --root <dir>
replay <path>`). Routes are far too long to try every glyph combination,
and the game never tells you how a glyph moves you — it will demonstrate
single steps on request, but each container gets only a small shared
allowance of demonstrations before the game stops answering, nowhere near
enough to feel your way through a room move by move. The exact output
shape for all three commands, and that demonstration channel, are described
in `/app/glyph-mill/RECOVERY-CONTRACT.md`.

You play as an unprivileged user — no debugger on the game, no peeking at
its file descriptors, and no reading anything under the test/solution
directories. Scoring also re-runs all three commands against edited copies
of the game (different rule files, mutated hints, moved salts/targets/
beacons), so nothing can be cached or hardcoded from the original install,
and any observation of the game you report has to be genuine for that
exact copy — the scorekeeper can tell the difference from a guess.
