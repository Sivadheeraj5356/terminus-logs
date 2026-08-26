# East and west crystallization arms disagree with rake surveys on multi-day brine

- **UUID:** `5e2448d7-3fca-4f7b-9b5d-e838f740f9df`
- **Slug:** `east-and-west-crystallization-arms-disagree-with-rake-survey`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

East and west crystallization arms disagree with rake surveys on multi-day brine campaigns. Single-day simulation traces look fine.

Continues from mid-tape checkpoints and pack swaps without a cold restart leave routing and front advances out of line with field measurements. `/app/bin/pond_ctl` is the pond simulation driver.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
