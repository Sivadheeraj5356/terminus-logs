# Build obligations

The tick loop (`internal/pipeline/run.go`), profile loader, fixture catalog, audit writer, metrics helpers, runner shell (`tools/runner.sh`), and offline verifier digest helpers are **provided**. Every function marked `// Stub:` in the Go tree must be implemented so bundled profiles produce `/app/output/schedule_audit.json` matching `schedule_audit_schema.md`.

Stub builds complete `linear_smoke` within documented bounds but stall or fail parity checks on diamond, gradual, fan-in, and cascade_wave graphs. Checkpoint restore and `checkpoint_chain` runs must reach bitwise parity with steady schedules for the same profile and seed.

## Coordination surface

Implement stub packages under:

- `vein/` — output exclusivity on submit, publish visibility, writer release, readability
- `weft/` — dependency ready-set and admission delay
- `drift/` — ready queue dispatch width
- `slate/` — boundary capture before reload
- `thaw/` — cold reload after a boundary
- `rift/` — visibility epoch after publish when `strict_deps` is enabled
- `spine/` — chain boundary normalization
- `grove/` — lane seal digest for checkpoint runs

The stub modules interact: output visibility, writer leases, dispatch width, capture FIFO order, reload semantics, visibility epochs, chain boundaries, and seal binding must agree across steady, `checkpoint_resume`, and `checkpoint_chain` run modes.

## Observable contract

Read `schedule_audit_schema.md` for digest formats, partition ledger rules, dispatch-width invariants, strict dependency tick gaps, and per-profile completion bands. Read `operations.md` for run modes and bundled profiles.

Rebuild both driver binaries after source changes:

```bash
cd /app/environment
go build -trimpath -ldflags="-s -w" -o /app/bin/dschedsim ./cmd/dschedsim
go build -trimpath -ldflags="-s -w" -o /app/bin/sched_probe ./cmd/sched_probe
```

`runner.sh` refreshes both binaries when either is missing or when Go sources are newer than either binary.

Hand-written audit JSON or profile edits are insufficient.
