# Shuffleboard rink operators run a terminal playtest claim board under /app. The

- **UUID:** `9df3a13e-2ff9-435b-a5cf-1a8be0e69667`
- **Slug:** `shuffleboard-rink-operators-run-a-terminal-playtest-claim-bo`
- **Category:** games
- **Difficulty:** hard

## Summary

Shuffleboard rink operators run a terminal playtest claim board under /app. The simulated court already loads layouts and wax-lot manifests.

Your job is to finish the combinatorial planner so exclusive wax lanes are allotted under friction-band game rules and a sealed claim ledger is published for playtest review. The simulator must chalk an intermediate slate, then allot from that slate alone, and emit a deterministic claim ledger for the simulated match window.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
