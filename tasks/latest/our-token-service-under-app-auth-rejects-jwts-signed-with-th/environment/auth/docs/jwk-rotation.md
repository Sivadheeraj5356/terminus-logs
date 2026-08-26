# JWK rotation

During the grace window after rotation, tokens signed with either the active or retiring key must validate when the JWT header `kid` matches a published key.

- Grace duration comes from `/app/auth/keys/rotation-state.json` (`grace_seconds`, measured from `rotated_at`). When it disagrees with `[rotation] grace_seconds` in `/app/auth/config/service.toml`, the rotation-state file wins.
- The grace window includes its final second (`now <= rotated_at + grace_seconds`).
- After grace expires, only the active key validates.
- Missing or unknown `kid` must reject the token.
- Algorithm must be `EdDSA` with curve `Ed25519`.

Published keys live under `/app/auth/keys/` as `jwk-active.json` and `jwk-retiring.json`.
