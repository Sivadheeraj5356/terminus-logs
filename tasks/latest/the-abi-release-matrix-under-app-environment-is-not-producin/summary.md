# The ABI release matrix under /app/environment is not producing a trustworthy rel

- **UUID:** `cd547b19-3d4d-4daa-a852-31c37e0d2d7c`
- **Slug:** `the-abi-release-matrix-under-app-environment-is-not-producin`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The ABI release matrix under /app/environment is not producing a trustworthy release. The artifacts that are published are produced by the SDK build process, but they do not hold together in their published form.

The record of the lane that is written by the ABI generator does not agree with the compiled probe’s observation of the lane. Fix the pipeline source under /app/environment.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
