Our token service under `/app/auth` rejects JWTs signed with the retiring key even though we are still inside the rotation grace window. The full JWK rules live in `/app/auth/docs/jwk-rotation.md`.

Fix kid lookup and grace handling in `/app/auth/cmd/tokensvc` and `/app/auth/internal/jwk`. While grace is open, tokens signed with either the active or retiring published key must validate when the header `kid` matches. The grace window includes its last second: at `rotated_at + grace_seconds` the retiring key must still work; one second later it must not. After grace, only the active key may validate.

Grace duration and `rotated_at` must come from `/app/auth/keys/rotation-state.json`. Do not use the fallback `[rotation] grace_seconds` value from `/app/auth/config/service.toml` when the two disagree. Reject tokens with a missing or unknown `kid`.

Rebuild with `/app/auth/bin/build.sh` after code changes. Check behavior with `/app/auth/bin/tokensvc.sh validate <token>`. You can shift the service clock for manual checks by exporting `AUTH_CLOCK_EPOCH` before running validate.
