# A PKIX chain-validation lab under `/app` regressed following reload-frame work.

- **UUID:** `c4b1314f-7e2b-4798-aad5-d4b802d9839b`
- **Slug:** `a-pkix-chain-validation-lab-under-app-regressed-following-re`
- **Category:** security
- **Difficulty:** medium

## Summary

A PKIX chain-validation lab under `/app` regressed following reload-frame work. `/app/bin/run_chainlab` reads `/app/data/rotation_spec.txt` and publishes `/app/output/trace.json` with `/app/output/readout.csv`, but isolated replay from `/app/target/release/probe` reports different generation samples, link carry, consult refusal, and row mapping on identical rotation inputs.

Multi-tick cases show blk_marks climbing from a stale baseline. Link carry overshoots or lags the live peak.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
