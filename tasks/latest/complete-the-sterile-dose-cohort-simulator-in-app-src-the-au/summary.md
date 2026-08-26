# Complete the sterile-dose cohort simulator in `/app/src`. The authoritative scie

- **UUID:** `48be4670-92a1-4d47-9dd0-f56a6c32920a`
- **Slug:** `complete-the-sterile-dose-cohort-simulator-in-app-src-the-au`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Complete the sterile-dose cohort simulator in `/app/src`. The authoritative scientific and file contract is `/app/docs/model_contract.md`.

It combines time-dependent assay decay, correlated uncertainty groups, substitute materials, discrete vial consumption, chronological inventory events, repeated priming cycles, open-vial stability episodes with post-opening potency decay and uncertainty growth, order budgets, bounded workload limits, and a cohort-wide lexicographic allocation objective. The implementation must apply the contract to any valid input directory, produce the exact deterministic `amberglass.v6` report requested by the caller, and fail closed on invalid input while removing a stale requested output.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
