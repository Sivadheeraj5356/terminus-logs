# This Node.js monorepo, at present, fails restrictively during normal dependency

- **UUID:** `fe10e985-b55c-4f12-b571-0fe9310543d3`
- **Slug:** `this-node-js-monorepo-at-present-fails-restrictively-during`
- **Category:** build-and-dependency-management
- **Difficulty:** medium

## Summary

This Node.js monorepo, at present, fails restrictively during normal dependency resolution. However, get the repository back to a fully working state.

Make only the changes strictly necessary to resovle especially the ANSI-related problem area (and not ECMA-48/ISO standards). Regarding this, missing fixtures/packages can be restored (if needed) from upstream source, the reference commit is at '3e59443be029e99d2b457bb43f682feb5ebcd2e0'.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
