# # Branch tracker

- **UUID:** `11e7ddd8-15da-4ffa-9d27-01149a2cfee3`
- **Slug:** `branch-tracker`
- **Category:** scientific-computing
- **Difficulty:** unknown

## Summary

Implement `trace_branch` in `/app/environment/src/continuation.cpp`. It is currently a stub that returns nothing.

Two discretised boundary-value problems, each carrying a parameter `lambda`, are fully specified in `/app/environment/docs/problem.md`. Each one's solution set is a curve in `R^16`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
