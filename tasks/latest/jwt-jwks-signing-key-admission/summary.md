# # JWT JWKS Signing-Key Admission

- **UUID:** `cff50367-5b4b-48b3-8434-f580bb9a202d`
- **Slug:** `jwt-jwks-signing-key-admission`
- **Category:** security
- **Difficulty:** hard

## Summary

Security operators on JWT/JWKS trust boundaries enforce signing-key admission and revocation from local JWKS tier trees under `/app/environment/fixtures`. During ordinary rotate, retire, and peer-realm inherit work, a short local pulse probe can look fine while `/app/output/freshness-report.json` still admits withdrawn kids, lets weaker cache/tenant material override stronger issuer policy, drops inherited peer kids across the realm trust boundary, or leaves a stale rotation seal in force.

Those are authorization failures: a retired signing kid must stay denied, stronger issuer policy must win, and foreign-realm residue must not cross the active profile principal. Implement JWT/JWKS signing-key admission controls under `/app/environment` from the authorization specification in `/app/environment/docs/contract.md` so `/app/bin/mux audit --profile <name>` regenerates `/app/output/freshness-report.json` through the normal admission path for the shipped `amber`, `beryl`, and `onyx` trust realms.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
