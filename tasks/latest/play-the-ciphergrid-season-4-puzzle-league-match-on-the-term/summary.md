# Play the CipherGrid season-4 puzzle-league match on the terminal board. Players

- **UUID:** `26a81102-559c-4a42-b276-46af76d78e9c`
- **Slug:** `play-the-ciphergrid-season-4-puzzle-league-match-on-the-term`
- **Category:** games
- **Difficulty:** hard

## Summary

Play the CipherGrid season-4 puzzle-league match on the terminal board. Players score moves from the season archive under `/app/data/season4/` (cells, glyphs, move tape, published scorecard).

Run `/app/bin/cipherleague score --archive DIR --out REPORT.json` to tally the match and write the sealed scorecard. Combo streaks, rivalry clashes, and dotted echo edges on the board map follow `/app/data/season4/scorecard.md` and the match rules under `semantics` in `/app/schema/ciphergrid-puzzle-league.schema.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
