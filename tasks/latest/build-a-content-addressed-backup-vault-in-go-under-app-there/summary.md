# Build a content-addressed backup vault in Go under `/app`. There is no starter c

- **UUID:** `46c2a3b0-a287-4a6d-8389-8a3fbae43b65`
- **Slug:** `build-a-content-addressed-backup-vault-in-go-under-app-there`
- **Category:** security
- **Difficulty:** hard

## Summary

Build a content-addressed backup vault in Go under `/app`. There is no starter code.

Read `/app/data/manifest.json` and each job config, pull the pinned policy material from `/app/data/endpoints.json`, walk each source tree, split file bodies with the gear-table CDC in `/app/spec/SPEC.md`, deduplicate into a shared chunk store, and write the batch plus per-job artifacts including HMAC attestations and the hash-chained ledger. When `/app/resources/remote_catalog/extra_jobs.json` is present, append those jobs after the main manifest.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
