# Rebuild the stub engine under /app/keyshare_engine into the witness binary at /a

- **UUID:** `be7ed9f0-4c00-4873-b43c-f398c9247298`
- **Slug:** `rebuild-the-stub-engine-under-app-keyshare-engine-into-the-w`
- **Category:** security
- **Difficulty:** hard

## Summary

Rebuild the stub engine under /app/keyshare_engine into the witness binary at /app/bin/keyshare_witness so one run merges the three shards under /app/data/handshake_capture in time order, walks each observation through the gate ladder type, required, empty offered, service, banned or rescued, duplicate, quota, rate, then phase with strength, and writes the report to /app/output/expected.json. A rerun must reproduce identical bytes and leave every shard untouched.

Each line carries observation_id, service_id, observed_ts_ns, offered_groups, client_id. A wrongly typed field earns REJECTED_TYPE, a missing field INVALID.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
