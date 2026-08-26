# splicekit

Scientific-computing undersea WDM optical-channel and Raman-pump caselab. Scenario fixtures drive wavelength continuity, regenerator remux, Raman cool-residual budgets, demand ranking, path tie-breaks, and peering settlement. The `splicectl` operator and `oxk-cli` numeric kernel implement the policies in `docs/contract.md`.

## Build

```bash
cd /app/environment/oxk && cargo build --release --locked
cp target/release/oxk-cli /app/bin/oxk-cli
cd /app/environment && go build -o /app/bin/splicectl ./cmd/splicectl
```

## Quick check

```bash
splicectl reset
splicectl run eq_pacific
splicectl run eq_cap_bind
splicectl status
splicectl publish
```

## PATH

Runtime expects `PATH` to include `/usr/local/cargo/bin:/usr/local/go/bin:/app/bin` ahead of system bins so `cargo`, `go`, `oxk-cli`, and `splicectl` resolve consistently.

## Fixtures

Scenario fixtures live under `/app/data/scenarios/`. The image also keeps a pristine copy at `/opt/splicekit/scenarios-pristine` for offline restore workflows.
