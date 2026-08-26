# # Cryptographic Audit Log Verifier

- **UUID:** `7a9cc2cb-1451-41b7-83e1-5e8b2b3cfda2`
- **Slug:** `cryptographic-audit-log-verifier`
- **Category:** security
- **Difficulty:** hard

## Summary

A cryptographic audit log validation pipeline lives under `/app/src/`. The verifier reads append-only log chains stored in segment files and produces a deterministic JSON validation report.

The implementation is split across cooperating modules, but multiple independent defects remain. Diagnose and repair the pipeline so that it validates arbitrary audit logs correctly.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
