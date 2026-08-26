# Architecture

Offline `linkctl` daemon under `/app/environment` with packages:

- `reg/` — class-aware incremental merge (`/app/environment/reg/m7_apply.go`)
- `lse/` — grant feed replay with epoch and fence (`/app/environment/lse/w4_epoch.go`)
- `pub/` — planned vs committed sealing (`/app/environment/pub/x2_seal.go`)
- `wal/` — append-only frames (`/app/environment/wal/frame.go`)
- `qtn/` — quarantine ledger (`/app/environment/qtn/gate.go`)
- `shim/` — foreign row loader
- `emit/` — FIB, link status, journal, fingerprint helpers
- `engine/` — cold boot, apply, recover (`/app/environment/engine/run.go`)
- `rcv/` — recovery tip helper for sealed WAL frames
- `cmd/linkctl/` — boot, reconfigure, recover (purge-history disabled)

Fixtures live under `/app/data/topology_w3/`; grant events in
`/app/var/grant_feed.jsonl`. Operator-visible schemas and invariants are in
`/app/environment/docs/operator_contract.md` and
`/app/environment/docs/network_policy.md`.
