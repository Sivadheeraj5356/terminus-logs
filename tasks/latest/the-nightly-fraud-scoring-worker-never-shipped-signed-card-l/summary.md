# The nightly fraud scoring worker never shipped — signed card-ledger batches are

- **UUID:** `7eed578d-bc0f-4fec-9159-45f76fd558e1`
- **Slug:** `the-nightly-fraud-scoring-worker-never-shipped-signed-card-l`
- **Category:** security
- **Difficulty:** medium

## Summary

The nightly fraud scoring worker never shipped — signed card-ledger batches are sitting unverified and job `JOB-20250620-001` is stuck queued in `/var/lib/ops/ops.db`. Ops wants a C worker built under `/app` (Makefile + `risk_worker` binary) per `/app/data/policy/risk_policy_manual.txt`.

Place all `.c` and `.h` source files and the Makefile directly under `/app/` in a flat layout — subdirectories such as `/app/src/` are not accepted by the build artifact checks. Milestone 1 is ledger provenance only: implement `verify-ledger` on `/app/risk_worker` per the policy manual.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
