# Operator runbook

## Build

`/usr/local/cargo/bin/cargo build --release --locked --manifest-path /app/environment/Cargo.toml`

Release binary path: `/app/environment/target/release/relayctl` (installed to `/app/bin/relayctl`).

## Run

`/app/bin/relayctl run` with:

- `--policy PATH`
- `--root PATH`
- `--state PATH`
- `--seed INT`
- `--report PATH`
- `--journal PATH`
- `--trace PATH`
- `--phase populate|idle|verify|all`
- `--workload-rounds INT` (optional partial rounds)
- `--shard-profile all|primary`

## Local mock shards

Integration runs against local mock shard TCP servers that mimic idle-close behavior on quiet pooled connections. Start mock shards on the policy shard host/port pairs before exercising relayctl in idle or all phases; tear them down cleanly when finished.

Relay runs persist coordinator state in `state.db` beside the report paths under `/output/`.

Do not edit `/app/fixtures/workloads/smoke_4.json` or `smoke_16.json`.
