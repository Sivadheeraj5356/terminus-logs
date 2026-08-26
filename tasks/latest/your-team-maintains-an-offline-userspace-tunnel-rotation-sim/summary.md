# Your team maintains an offline userspace tunnel-rotation simulator under `/app/e

- **UUID:** `2d42987a-a66e-46f2-90d1-36e33d4b6f6e`
- **Slug:** `your-team-maintains-an-offline-userspace-tunnel-rotation-sim`
- **Category:** security
- **Difficulty:** hard

## Summary

Your team maintains an offline userspace tunnel-rotation simulator under `/app/environment`. After the documented stage pass, peers lose mux coherence during apply replay while a local status view can still read healthy, and sparse run logs can look settled while the terminal reconcile report disagrees across primary peer ids.

Repair the C++ sources so the workflow in `/app/environment/docs/operator_cmds.txt` regenerates `/app/output/psk_rotate_report.json`, sparse phase rows under `/app/output/run_traces/`, and witness bytes at `/app/environment/w8g/staged/w8_chain.bin`. Coherence rules, formulas, schema, and profile sequencing are in `/app/environment/docs/public_contract.md`; data index in `/app/environment/docs/formal_rules.md`; report shape in `/app/environment/schemas/row_wg.schema.json`; sparse trace subset in `/app/environment/docs/trace_subset.txt`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
