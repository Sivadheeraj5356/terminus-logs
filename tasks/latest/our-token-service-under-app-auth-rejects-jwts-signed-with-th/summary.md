# Our token service under `/app/auth` rejects JWTs signed with the retiring key ev

- **UUID:** `40e57f12-6376-4580-b652-323845c350bb`
- **Slug:** `our-token-service-under-app-auth-rejects-jwts-signed-with-th`
- **Category:** security
- **Difficulty:** hard

## Summary

Our token service under `/app/auth` rejects JWTs signed with the retiring key even though we are still inside the rotation grace window. The full JWK rules live in `/app/auth/docs/jwk-rotation.md`.

Fix kid lookup and grace handling in `/app/auth/cmd/tokensvc` and `/app/auth/internal/jwk`. While grace is open, tokens signed with either the active or retiring published key must validate when the header `kid` matches.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
