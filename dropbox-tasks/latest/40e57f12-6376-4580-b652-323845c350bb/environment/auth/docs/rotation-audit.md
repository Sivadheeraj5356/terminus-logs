# Rotation audit export

`/app/auth/bin/export-audit.sh` writes `/app/auth/out/rotation-audit.jsonl`.

Each line is one JSON object. Every line includes `event_seq`, `event_type`, and `ts`. Other fields depend on the event type. Unused fields are omitted, not set to empty strings:

| `event_type`    | fields present                         |
|-----------------|----------------------------------------|
| `key_promoted`  | `event_seq`, `event_type`, `kid`, `ts` |
| `key_retired`   | `event_seq`, `event_type`, `kid`, `ts` |
| `token_revoked` | `event_seq`, `event_type`, `jti`, `ts` |

## Event sequence assignment

Fixed rotation events always use the same sequence numbers and timestamp offsets from `clock_epoch` in `/app/auth/config/service.toml`:

| `event_type`    | `event_seq` | `ts` offset (seconds) |
|-----------------|-------------|------------------------|
| `key_promoted`  | 1           | 0                      |
| `key_retired`   | 2           | 10                     |

Each revoked `jti` in the ledger becomes one `token_revoked` line. Sort revoked jtis alphabetically ascending, then assign `event_seq = 100 + i` and `ts` offset `20 + i` to the i-th jti (zero-based). Write all lines sorted by ascending `event_seq`.

## Token validation (lifecycle)

During `tokensvc validate`:

- Reject when the token `jti` is present in `/app/auth/data/revocations.db`.
- When the JWT includes an `exp` claim, reject if `exp` is strictly before the service clock (`clock_epoch`, overridable via `AUTH_CLOCK_EPOCH`).
- Tokens with no `exp` claim must still validate when signature, `kid`, grace rules, and revocation checks pass.
