# The security release authority uses an offline Rust attestation gate in `/app/ta

- **UUID:** `c1be8239-61e2-4b2d-bb37-db4341796f0b`
- **Slug:** `the-security-release-authority-uses-an-offline-rust-attestat`
- **Category:** security
- **Difficulty:** hard

## Summary

The security release authority uses an offline Rust attestation gate in `/app/task_file/logseal` to decide whether signed artifacts remain trustworthy under signer compromise, transparency-log failure, and dependency-amplified blast-radius scenarios. Implement the gate so it produces the deterministic security decision report defined in `/app/task_file/logseal_contract.md`, including evidence failures, resilience cuts, recovery certificates, and release-policy outcomes.

Run the security gate as `cargo run --release --bin logseal -- <input_dir> <output_dir>`. It must read the eight evidence and policy files named in the contract from `<input_dir>`, create `<output_dir>` when necessary, and write exactly one file: `<output_dir>/report.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
