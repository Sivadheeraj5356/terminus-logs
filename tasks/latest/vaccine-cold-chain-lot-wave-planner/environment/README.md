# immunocold lot-wave planning lab

Vaccine cold-chain lot-wave allocation with shared FEFO inventory depletion, epidemiological dose-interval scheduling, infection projection, pallet temperature packing via `pkmerge`, and regional equity reconciliation.

Build `immunoflow` from `/app/environment` with `go build -o /app/bin/immunoflow ./cmd/immunoflow`. Rebuild `pkmerge` from `/app/environment/pkmerge` with `cargo build --release` and install the binary at `/app/bin/pkmerge`. The golang base provides `/usr/local/go/bin/go` on `PATH`; the image already ships a prebuilt `pkmerge` at `/app/bin/pkmerge`.

Canonical wave-3 pipeline:

```
immunoflow bench reset
immunoflow plan-wave --lab /app/data/immunolab --wave 3 --out /app/output/allocation_plan.json
immunoflow bind-lanes --wave 3 --plan /app/output/allocation_plan.json --out /app/output/coldchain_audit.json
immunoflow schedule-doses --lab /app/data/immunolab --dose1-wave 3
immunoflow reconcile-equity --lab /app/data/immunolab --plan /app/output/allocation_plan.json
immunoflow project-infections --lab /app/data/immunolab --plan /app/output/allocation_plan.json
```

Behavioral contracts live in `/app/environment/docs/contract.md`.

Verifier companion scripts under `/tests/immunoflow_ref.py` may shell out to `sha256sum` for digest checks.
