`bayctl` exposes host and user-namespace PAM faillock authentication views for
Linux account-lockout security testing. Failed-login enforcement, unlock of the
authoritative auth store, and audit actor scope must remain consistent across
those privilege boundaries.

## Graded binary

Operators grade the binary at `/app/bin/bayctl`. Image build preseeds that
path; later source edits are inert until you rebuild to the same path:

```bash
go build -o /app/bin/bayctl /app/cmd/bayctl
```

## CLI surface

| Command | Flags | Success stdout | Other stdout |
|---------|-------|----------------|--------------|
| `setup` | `--scenario <path>` | `setup complete` | |
| `attempt` | `--password <secret>` | `attempt accepted` | `attempt rejected` |
| `enter-ns` | _(none)_ | `enter-ns complete` | |
| `unlock` | `--principal <name>` | `unlock complete` | `unlock failed` |
| `ingest` | `--batch <name> --events <jsonl>` | `ingest complete` | `ingest skipped` |
| `rebuild` | _(none)_ | `rebuild complete` | |
| `report` | `--out <path>` (default `/app/output/lock_ledger.json`) | `report complete` | |
| `audit` | `--out <path>` (default `/app/output/lock_audit.json`) | `audit complete` | |

`ingest` requires both `--batch` and `--events`. Re-importing an existing
batch name skips and prints `ingest skipped`.
