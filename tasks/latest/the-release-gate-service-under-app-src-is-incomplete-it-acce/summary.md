# The release-gate service under `/app/src/` is incomplete. It accepts evaluation

- **UUID:** `29944a6c-ea19-4149-8e92-c3d79349152f`
- **Slug:** `the-release-gate-service-under-app-src-is-incomplete-it-acce`
- **Category:** security
- **Difficulty:** hard

## Summary

The release-gate service under `/app/src/` is incomplete. It accepts evaluation requests over HTTP and is supposed to decide whether a signed Git release tag is eligible for promotion, but currently approves everything.

Fix the implementation so it correctly enforces the policy. The sole authority for policy behavior is `/app/standard/cdss_v4.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
