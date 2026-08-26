# Beat Every Room in Glyph Mill

A single-step Terminal-Bench task built around a terminal walking-puzzle
game, Glyph Mill. Each room's context lives in LMDB and its rule packs —
including an overlay file picked by hidden logic inside the compiled game —
load dynamically from YAML/TOML files, so winning every room means watching
the running game rather than guessing at its rules. Routes are long enough
that naive sequence enumeration is infeasible, and how a glyph moves the
walker is never written down anywhere readable: the game will demonstrate
single steps on request, but only under a small allowance shared across the
whole container, so the player has to work the movement rule out from a
handful of demonstrations and then plan every room's winning route with a
layered search of their own.
