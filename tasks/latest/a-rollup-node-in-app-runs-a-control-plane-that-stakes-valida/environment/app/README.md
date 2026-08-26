# keystone

A standard-library Rust HTTP control plane for a rollup blockchain node. Accounts register and stake
validators into an active set, propose L2 blocks that a validator committee finalizes by weighted
endorsement, bridge L1 deposits into L2 state through a relayer, and run governance referenda with
delegable ballots.

- Build: `cargo build --release --locked`
- Run: serves on `127.0.0.1:8847` by default (`KEYSTONE_ADDR` overrides). Audit log at `/app/audit.log`
  (`KEYSTONE_AUDIT_PATH` overrides).
- Auth: `POST /v1/auth/token` returns a bearer token; send it as `Authorization: Bearer <token>`.

See `docs/api.md` for the full API reference and `docs/architecture.md` for the module map.
