# The Rust project in `/app` builds a binary called `cryoctl` that maintains a

- **UUID:** `4fa720b2-0e19-4206-a330-73e7a27d1078`
- **Slug:** `the-rust-project-in-app-builds-a-binary-called-cryoctl-that`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The Rust project in `/app` builds a binary called `cryoctl` that maintains a per-cryostat boil-off warden for a bank of cryogenic helium storage vessels. It reads a single JSON object from stdin describing a grace allowance and a stream of timestamped events — cryostats crossing above and below their relief threshold, transfer-line purge windows, and reports — replays them in order against a continuous-time monitor, and writes one JSON object to stdout with an `audit` trail, the closed `boiloff` intervals, and per-cryostat exposed aggregates.

The current build handles the common case — a cryostat that dwells above its relief threshold past the grace allowance and then settles — but mishandles how the boil-off accrual interacts with transfer-line purge windows and with at-risk stretches that cross the allowance between events, so some boil-off intervals and exposed totals come out wrong. Fix the implementation so every case matches the specification.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
