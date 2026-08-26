# # Beat Every Room in Glyph Mill

Submission: `0703f1cf-1690-4142-a968-808841968442`  
Slug: `beat-every-room-in-glyph-mill`  
Latest archive: `0703f1cf-1690-4142-a968-808841968442_submission_2026-07-15T13_04_29.095Z.zip`  
Revisions: 4

## Task summary

Glyph Mill is an old terminal game sitting at `/app/glyph-mill`. Each room is a grid you walk one cell at a time by feeding it a sequence of glyphs, and you win a room by landing on its target after an exact number of moves, while also passing through any beacon cells it demands along the way (a beacon at move index N means you must be standing on that cell after exactly N moves, index 0 being the start cell before any move has been made). Nobody kept notes on how the game works, though — which YAML/TOML rule pack a room actually draws from (part of that pick happens inside the compiled game, not something you can read off a hint file or a directory listing) or how feeding it a glyph moves you on the grid. Win every room. Deliver your playbook as `/app/recovered/glyph_tool.py` with three subcommands, each writing JSON to `--out <path>` for a given `--root <dir>`: `discover` (for each room, its LMDB hint plus exactly which rule files the game really reads for it, caught in the act rather than guessed from the layout), `normalize` (fold everything `discover` found into one flat rulebook), and `solve` (a winning move sequence per room, using only that room's own glyphs, accepted by `glyph-mill --root <dir> replay <path>`). Routes are far too long to try every glyph combination, and the game never tells you how a glyph moves you — it will demonstrate single steps on request, but each container gets only a small shared allowance of demonstrations before the game stops answering, nowhere near enough to feel your way through a room move by move. The exact output shape for all...

Required artifacts include: `/app/glyph-mill`, `/app/recovered/glyph_tool.py`, `/app/glyph-mill/RECOVERY-CONTRACT.md`.

Author anonymous tagged this **hard** games task (terminal-game, walking-puzzle, maze, lmdb, yaml, toml).

Time estimates: expert ~210 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `0703f1cf-1690-4142-a968-808841968442_submission_2026-07-15T13_04_29.095Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
