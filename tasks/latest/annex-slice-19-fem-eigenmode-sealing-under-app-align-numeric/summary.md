# Annex-slice-19 FEM eigenmode sealing under `/app`. Align numerical authorities a

- **UUID:** `23e9883f-fddc-451d-9d26-b18dd57b1e56`
- **Slug:** `annex-slice-19-fem-eigenmode-sealing-under-app-align-numeric`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Annex-slice-19 FEM eigenmode sealing under `/app`. Align numerical authorities and peel timing under `/app/data` so panels conserve.

Clear stale tip, seal.bind, and WAL under `/app/data/ms_store`, then rematerialize `/app/output/invariant_proof_log.json` via `/app/scripts/proof_run.sh`. Treat mode_seal as sealed.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
