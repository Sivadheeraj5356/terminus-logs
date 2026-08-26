# Fix the Go source for `sgfpack` under /app/environment/tools/sgfpack, then use t

- **UUID:** `7b058460-0e5c-45d8-9110-49e077a66a8c`
- **Slug:** `fix-the-go-source-for-sgfpack-under-app-environment-tools-sg`
- **Category:** games
- **Difficulty:** hard

## Summary

Fix the Go source for `sgfpack` under /app/environment/tools/sgfpack, then use the repaired command to reconcile the Harbor House 5x5 Cup under /app/workspace. The current rounds register, current SGF records, repair state, and output pack may be stale or corrupted; the authorities are the rules document, camera move logs, referee cards, and active adjudication journal entries.

A correct repair rebuilds /app/workspace/register/rounds.tsv, /app/workspace/records/current/*.sgf, and /app/workspace/register/repair_state.json from those authorities, including positional-superko forfeits and normal scored games. After the workspace is repaired, regenerate /app/output/sgf-pack with the normal CLI path.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
