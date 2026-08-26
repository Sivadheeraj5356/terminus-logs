# A sccache release guard must close a reproducible build attestation from depende

- **UUID:** `299441da-a136-484d-b73c-1f698f87663b`
- **Slug:** `a-sccache-release-guard-must-close-a-reproducible-build-atte`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

A sccache release guard must close a reproducible build attestation from dependency lock pins, define-order lockfile traces, and compiler-wrapper SBOM hash segments before publish clears. Produce `/app/output/kq_report.json` through `/app/environment/tools/kq_run`.

The lockfile reload rules, supply-chain pin blend, release-guard witness, and reproducibility digest are specified in `/app/environment/docs/kq_contract.md`, `/app/environment/docs/kq_notes.md`, and `/app/environment/docs/build-cache-sbom-lockfile.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
