# Play the CipherGrid season-4 puzzle-league match on the terminal board. Players 

Submission: `26a81102-559c-4a42-b276-46af76d78e9c`  
Slug: `play-the-ciphergrid-season-4-puzzle-league-match-on-the-term`  
Latest archive: `26a81102-559c-4a42-b276-46af76d78e9c_submission_2026-07-20T09_58_04.427Z.zip`  
Revisions in Dropbox: 5

## Task summary

Play the CipherGrid season-4 puzzle-league match on the terminal board. Players score moves from the season archive under `/app/data/season4/` (cells, glyphs, move tape, published scorecard). Run `/app/bin/cipherleague score --archive DIR --out REPORT.json` to tally the match and write the sealed scorecard. Combo streaks, rivalry clashes, and dotted echo edges on the board map follow `/app/data/season4/scorecard.md` and the match rules under `semantics` in `/app/schema/ciphergrid-puzzle-league.schema.json`. Per-move base points equal glyph weight plus twice the count of orthogonally adjacent same-family solution cells, rounded half-away-from-zero to two decimals. Multiply that by pressure `1.0 + 0.05 * R` where `R` counts same-family solution cells absent from earlier tape rows, then round again before summing; round each player total the same way. Combo streaks group a player's moves by tick then cell_id and grow when consecutive solution families match; each continued step after the first adds `0.25 * (streak_len - 1)` before rounding `combo_points`. Rivalry awards `0.5` to each side whenever two different players' moves sit within one tick, on orthogonal neighbors, with a shared solution family; emit rounded `rivalry_points` and `rivalry_digest`. Dashed board-map edges mark same-family adjacencies; dotted echo edges mark same-family adjacencies where both cells appear on the tape.

Required artifacts include: `/app/data/season4/`, `/app/bin/cipherleague`, `/app/data/season4/scorecard.md`, `/app/schema/ciphergrid-puzzle-league.schema.json`, `/app/var/match_chain_tip.txt`.

Author anonymous tagged this **hard** games task (puzzle-league, ciphergrid, board-match, combo-streak, rivalry-clash, graphviz-board).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `26a81102-559c-4a42-b276-46af76d78e9c_submission_2026-07-20T09_58_04.427Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
