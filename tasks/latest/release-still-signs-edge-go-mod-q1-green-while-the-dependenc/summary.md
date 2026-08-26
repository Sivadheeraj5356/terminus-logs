# Release still signs EDGE-GO-MOD-Q1 green while the dependency graph, live module

- **UUID:** `3fbf9b62-caa3-44f3-82be-20107b3e97da`
- **Slug:** `release-still-signs-edge-go-mod-q1-green-while-the-dependenc`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Release still signs EDGE-GO-MOD-Q1 green while the dependency graph, live module registry posture, and reproducibility certificate disagree on the escalated pins. Some members keep sailing through as if the frozen January pack were enough, advisory waivers that release engineering already recorded are not showing up that way, and the digest export that is supposed to seal the batch does not match what sign-off expects on the production track.

Bring the module dependency integrity gate under /app back in line so the compiled modgate entrypoint on PATH, run against the bundled primary manifest, prints MODGATE_OK and writes every contract-conforming artifact under /app/output. Observable shapes and invariants live in /app/docs/output-contract.md.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
