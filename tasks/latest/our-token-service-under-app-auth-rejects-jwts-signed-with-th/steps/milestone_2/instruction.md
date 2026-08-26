Revocations in `/app/auth/data/revocations.db` are not append-only. Re-revoking the same `jti` overwrites the prior row instead of leaving history untouched, which breaks our audit trail. The ledger contract is in `/app/auth/docs/revocation-ledger.md`.

Fix `/app/auth/internal/ledger` and rebuild with `/app/auth/bin/build.sh`. Each revoke must insert a new row only when that `jti` is not already recorded. Calling revoke again for the same `jti` must be a no-op: row count stays one, and `revoked_at` and `reason` must not change on the existing row. Different jtis must produce separate rows with increasing numeric ids.

Write `revoked_at` as RFC3339 UTC from the service clock defined in `/app/auth/config/service.toml` (`clock_epoch`, overridable via `AUTH_CLOCK_EPOCH`). Do not stamp revocations from wall clock time.

Use `/app/auth/bin/tokensvc.sh revoke <jti> [reason]` while testing. Inspect rows with sqlite3 against `/app/auth/data/revocations.db` if you need to confirm append-only behavior and stable timestamps on duplicate revoke.
