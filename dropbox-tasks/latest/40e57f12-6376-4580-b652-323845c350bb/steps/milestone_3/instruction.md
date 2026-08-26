Our auth service under `/app/auth` validates JWTs without consulting the revocation ledger, does not enforce `exp` correctly, and writes a non-deterministic rotation audit export. Export format and lifecycle rules are in `/app/auth/docs/rotation-audit.md`.

Wire ledger lookup into the validate path in `/app/auth/cmd/tokensvc` and `/app/auth/internal/validator`. After a successful signature and kid check, reject tokens whose `jti` is stored in `/app/auth/data/revocations.db`. If the JWT carries an `exp` claim, reject when `exp` is before the service clock from `/app/auth/config/service.toml` (honor `AUTH_CLOCK_EPOCH` when set). Tokens without an `exp` claim must continue to validate when they are otherwise good.

Fix `/app/auth/internal/audit` so `/app/auth/bin/export-audit.sh` writes `/app/auth/out/rotation-audit.jsonl` with fixed `event_seq` values, alphabetical ordering for revoked jtis, contract timestamp offsets, and lines sorted by ascending `event_seq` as described in the doc.

Rebuild with `/app/auth/bin/build.sh`. Test with `/app/auth/bin/tokensvc.sh validate <token>`, revoke, and `/app/auth/bin/export-audit.sh`.
