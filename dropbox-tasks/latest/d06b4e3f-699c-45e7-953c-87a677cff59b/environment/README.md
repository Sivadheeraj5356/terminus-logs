# chainaudit

Cryptographic tamper-evidence and integrity verification for the compliance
event store: every event is hash-chained into RFC 6962-style Merkle
checkpoints, HMAC-signed by an external key-management service, so that
unauthorized modification of a row after the fact is independently
detectable rather than merely logged. Two subcommands share one SQLite
database:

- `chainaudit verify --db <path> --out <path> [--kms-addr <url>]` recomputes
  and cryptographically re-verifies every stream's integrity status —
  content hashes, Merkle roots, and checkpoint signatures.
- `chainaudit compact --db <path> --out <path> --now-file <path>` prunes
  expired, fully-checkpointed events without weakening the tamper-evidence
  guarantee for what remains, and without pruning anything still under legal
  hold.

The exact wire format, hashing rules, checkpoint/signature contract, and
retention semantics are documented in `CHAINAUDIT-SPEC.md`.

## Layout

```
cmd/chainaudit/     CLI entrypoints (cobra)
cmd/mockkms/        local stand-in for the checkpoint-signing key service
internal/model/     row structs shared across packages
internal/canon/      canonical event encoding
internal/merkle/     RFC 6962-style hash tree and checkpoint tip chain
internal/kms/        client for the signing key service
internal/store/      SQLite access
internal/audit/      verify and compact business logic
data/                 chainaudit.db (SQLite) and NOW.txt (reference clock)
```

## Build

```
go build -mod=vendor -o /usr/local/bin/chainaudit ./cmd/chainaudit
```

The key service used by `verify` is already running at
`http://127.0.0.1:8500` inside this container.
