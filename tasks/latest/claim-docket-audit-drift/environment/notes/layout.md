# Source layout

- `internal/crc/` — frame checksum helpers
- `internal/frame/` — frame parsing and canonical JSON
- `internal/ingest/` — docket directory loading and fingerprint
- `internal/checkpoint/` — checkpoint sidecar loading
- `internal/digest/` — rolling digest links
- `internal/ledger/` — ledger settlement and metrics
- `internal/config/` — audit profile and region allowlist
- `internal/report/` — report assembly, persistence, and emit
- `cmd/claimdocketaudit/` — CLI entry
