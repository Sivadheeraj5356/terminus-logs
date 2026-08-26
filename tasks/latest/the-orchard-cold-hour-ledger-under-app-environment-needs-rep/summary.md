# The orchard cold-hour ledger under `/app/environment` needs repair. Rebuild the

- **UUID:** `5f068a1b-7c07-450e-9c4f-68f394628d61`
- **Slug:** `the-orchard-cold-hour-ledger-under-app-environment-needs-rep`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The orchard cold-hour ledger under `/app/environment` needs repair. Rebuild the Go CLI from source so replay mode regenerates deterministic `s7_ledger.jsonl`, `s7_audit.tsv`, and `replay_state.json` artifacts from manifest-relative inputs, while the original simple mode remains backward compatible.

The repaired pipeline must follow the contracts in `/app/environment/docs` for profile settings, environment overrides, sensor registry calibration, correction replay, Fahrenheit conversion, anchored bucket windows, interval credit, deterministic output, replay state, and atomic failure behavior.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
