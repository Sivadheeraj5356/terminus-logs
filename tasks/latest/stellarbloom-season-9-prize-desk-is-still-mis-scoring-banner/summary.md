# Stellarbloom Season 9 prize desk is still mis-scoring banner pulls before weeken

- **UUID:** `986ffe12-7ecb-4d08-bc89-157752212d0c`
- **Slug:** `stellarbloom-season-9-prize-desk-is-still-mis-scoring-banner`
- **Category:** games
- **Difficulty:** hard

## Summary

Stellarbloom Season 9 prize desk is still mis-scoring banner pulls before weekend payouts — the live fairness audit under `/app` has to match esports gacha policy. Note that code comments and docstrings may themselves contain errors.

Get `/app/bin/gachaudit` writing a trustworthy `/app/output/report.json` for the stellarbloom export (side scripts that skip the desk binary do not count). CLI flags, schema, MAC domains, pity gap, revision dedupe, ledger keys, and anomaly kinds are in `/app/docs/prize_desk_contract.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
