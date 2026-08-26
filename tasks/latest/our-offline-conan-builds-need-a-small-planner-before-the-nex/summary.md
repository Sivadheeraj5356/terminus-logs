# Our offline Conan builds need a small planner before the next CI image refresh.

- **UUID:** `0d572df7-f261-4ddb-984a-3e55c79d8ab7`
- **Slug:** `our-offline-conan-builds-need-a-small-planner-before-the-nex`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Our offline Conan builds need a small planner before the next CI image refresh. The planner has to preserve earlier lock decisions, account for feature or option growth across ordered stages, and decide whether existing artifacts can be reused.

Create an executable CLI at `/app/bin/conanplan`. The verifier runs it as `/app/bin/conanplan /app/input /app/output/plan.json` and also reruns the same executable against other compatible input directories.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
