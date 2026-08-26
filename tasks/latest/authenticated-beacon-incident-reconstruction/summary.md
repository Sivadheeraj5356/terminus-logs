# # Authenticated Beacon Incident Reconstruction

- **UUID:** `af9cf339-2a5e-442d-a69b-27154263704f`
- **Slug:** `authenticated-beacon-incident-reconstruction`
- **Category:** security
- **Difficulty:** hard

## Summary

This is an offline security-forensics and incident-reconstruction task. A monitoring station lost its trusted state after suspected telemetry forgery, replay, and cross-station credential misuse.

Recover the final trusted sensor dataset from the remaining untrusted binary beacon stream without allowing damaged, stale, unauthenticated, or invalidated evidence to alter later security decisions. Produce a single C11 source file at `/app/src/beacon_replay.c`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
