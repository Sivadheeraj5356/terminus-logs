# We need a deterministic link-plan utility for a build audit. Complete the intent

- **UUID:** `1c73c5a9-6581-46cd-b50b-d4e940874793`
- **Slug:** `we-need-a-deterministic-link-plan-utility-for-a-build-audit`
- **Category:** build-and-dependency-management
- **Difficulty:** medium

## Summary

We need a deterministic link-plan utility for a build audit. Complete the intentionally incomplete Go program in `/app/src/main.go` so `/app/build.sh` creates `/app/arcplan`, then run `/app/arcplan /app/linkcase /app/link-report.json`.

The starter currently handles only a small part of loose-object processing. The complete four-file contract is in `/app/link-model.md`: it includes transitive symbol aliases, strong and weak references, ordered `NEED` directives, normal/group/whole archive scans, COMDAT ownership, and provider precedence.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
