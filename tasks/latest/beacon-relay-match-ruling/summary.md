# # Beacon Relay match ruling

- **UUID:** `87a94d43-3e05-425b-8361-c8139cb3f2ce`
- **Slug:** `beacon-relay-match-ruling`
- **Category:** games
- **Difficulty:** hard

## Summary

Determine the best valid ruling package for the completed Beacon Relay match in `/app/match.json`. Re-read the file on every run and write `/app/output/result.json`.

The input has two unique lowercase `players`, a `claimant` among them, a nonnegative integer `budget`, `relay_requirements`, `coordination_costs`, `cells`, `units`, baseline `rounds`, `rulings`, and `dockets`. Cells are `{id:string,neighbors:[cell IDs...],move_cost:positive integer,beacon:nonnegative integer,recharge:nonnegative integer}`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
