# The host under `/app/environment` should make extension changes transactional: s

- **UUID:** `47c7cafc-75fe-40a8-9709-540760275e36`
- **Slug:** `the-host-under-app-environment-should-make-extension-changes`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The host under `/app/environment` should make extension changes transactional: stage payloads on disk, bump versions, undo following a bad step, and keep the published entitlement map aligned with what is actually loaded. Operators report three pain clusters.

After an interrupted bump, restart cannot tell which half-finished step to continue from even though a durable byte log exists. Undo puts payloads back but callers still see grants that should have vanished.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
