# The root CA that signed our east-west mTLS credentials is confirmed compromised,

- **UUID:** `9dc87873-29c5-4064-8182-29a6451f3d9d`
- **Slug:** `the-root-ca-that-signed-our-east-west-mtls-credentials-is-co`
- **Category:** security
- **Difficulty:** hard

## Summary

The root CA that signed our east-west mTLS credentials is confirmed compromised, so an attacker can impersonate every service that remains on the old credential generation. Produce the exact emergency rotation schedules for the three incident inventories described below.

Leave `/app/task_file/scan_input/` unchanged. The three incident inventories are `/app/task_file/scan_input/credential_incident.txt`, `/app/task_file/scan_input/credential_incident_b.txt`, and `/app/task_file/scan_input/credential_incident_c.txt`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
