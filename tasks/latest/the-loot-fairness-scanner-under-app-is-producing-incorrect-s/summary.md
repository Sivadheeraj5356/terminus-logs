# The loot fairness scanner under `/app` is producing incorrect session reports af

- **UUID:** `97fce60e-fc47-4d51-94ce-2c790b36a89a`
- **Slug:** `the-loot-fairness-scanner-under-app-is-producing-incorrect-s`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The loot fairness scanner under `/app` is producing incorrect session reports after a replay refactor. Fix the implementation by editing Go code only under `/app/faircore` and `/app/rollbench`; do not modify `/app/dropvault`, `/app/go.mod`, or `/app/Makefile`.

Behavior and output requirements are defined by `/app/dropvault/fairness_rules.json` and the rule files it references. Implement all of those rules exactly.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
