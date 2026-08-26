# This host runs an OpenSSL 3 ENGINE→provider migration steward under `/app/enviro

- **UUID:** `e36bdf4c-bef7-4d73-a5ea-e4c11ac8f88a`
- **Slug:** `this-host-runs-an-openssl-3-engine-provider-migration-stewar`
- **Category:** security
- **Difficulty:** hard

## Summary

This host runs an OpenSSL 3 ENGINE→provider migration steward under `/app/environment`. Prefer-arm property queries, provider activation order, and URI loader schemes decide which cryptographic arm is authorized to satisfy a case.

After migration, the graded matrix still publishes unauthorized outcomes: strict queries fall back off the prefer-arm, first-wins activation order collapses, and `slotA` rows keep the legacy engine URI scheme so material that should require the preferred arm still opens under `eng://`. Mid-cycle arming state under `/app/output/.ov_persist/` can leave a later suite able to seal with a stale nonce or a residue-shaped digest.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
