# Revocation ledger

Revocations persist in SQLite at `/app/auth/data/revocations.db`.

Schema:

```sql
CREATE TABLE revocations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  jti TEXT NOT NULL,
  revoked_at TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX idx_revocations_jti ON revocations(jti);
```

Rules:

- Append-only: never UPDATE or DELETE existing rows.
- Duplicate revoke for the same `jti` is a no-op (no second row).
- `revoked_at` uses RFC3339 UTC from the service clock (`clock_epoch` in `/app/auth/config/service.toml`, overridable via `AUTH_CLOCK_EPOCH`).
