# build_dependency_toolchain

- **UUID:** `f626bd08-a1fd-4033-a722-66c11c56b92f`
- **Slug:** `build-dependency-toolchain`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The regression commits are listed in `/app/reports/regression_commits.txt`. Fix `/app/repo` so `go test ./...` passes again.

The failures cross several packages — route matching, ledger persistence, dispatch ordering, and delivery retries all need to work together. A single `git revert` probably will not cut it because later commits sit on top of the broken code; repair the implementation on the current tip.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
