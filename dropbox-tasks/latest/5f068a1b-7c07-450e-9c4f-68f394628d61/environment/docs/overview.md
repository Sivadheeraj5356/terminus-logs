# Canopyledger overview

`canopyledger` is a Go CLI under `/app/environment` that rolls up orchard cold-hour credits from sensor temperature feeds.

## Modes

1. **Simple mode** — single profile TOML + sensor CSV → `s7_ledger.jsonl`. See `s7_rules.md`.
2. **Replay mode** — manifest-driven multi-file pipeline → `s7_ledger.jsonl`, `s7_audit.tsv`, `replay_state.json`. See `replay_manifest.md` and `output_contract.md`.

Build:

```bash
go build -o /tmp/orchard-ledger /app/environment/cmd/orchardledger
```

Fixtures live under `/app/environment/fixtures`. The default replay manifest is `replay_manifest.toml`.

## Packages

- `config` — profile TOML and env precedence
- `parse` — CSV reading loaders
- `accum` — interval credit and bucket windows
- `emit` — ledger and audit writers
- `manifest` — replay manifest parsing and path resolution
- `registry` — per-sensor units, offsets, active windows
- `corrections` — revision collapse
- `state` — input hashing and replay state
- `replay` — replay orchestration
