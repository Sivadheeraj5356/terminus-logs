# The Rust seating driver under `/app` still produces inconsistent live state when

- **UUID:** `ecacd7da-f89d-4706-9705-ba07177f1740`
- **Slug:** `the-rust-seating-driver-under-app-still-produces-inconsisten`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The Rust seating driver under `/app` still produces inconsistent live state when schedules combine repeated seat publications, cycle transitions, catalog probes, and failed runs. Repair the editable Rust sources under `/app/src` so module-level journal loading, replay, publication, digest, and recovery behavior exposed through the compiled binary is correct, not only static or hand-written output files.

Normal seat, recovery seat, and shift-table probe modes documented in `/app/docs/overview.md` must satisfy the observable contracts in `/app/docs/overview.md` and `/app/docs/runtime_notes.txt`, including correct live-ledger totals, cycle ownership, cache isolation, deterministic publication, and rollback behavior. Journal rows are applied in ascending `seq` order.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
