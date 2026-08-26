# Our GAA nanosheet tape-out lab needs numerical device calibration closure on the

- **UUID:** `6d680189-86a6-43d5-b2c3-604662096bb1`
- **Slug:** `our-gaa-nanosheet-tape-out-lab-needs-numerical-device-calibr`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Our GAA nanosheet tape-out lab needs numerical device calibration closure on the characterization kernel under /app before compact models can clear foundry signoff. Close the measured IV and CV sweeps against the fitted compact transistor model and publish /app/out/gaa_model.sp plus /app/out/model_validation.json from the bundled fixtures under /app/data/bundled and bounds at /app/config/parameter_bounds.toml.

Normative device physics, schemas, and numeric solver rules are in /app/docs/scientific-computing-workflow.md, /app/docs/device-characterization-contract.md, /app/docs/compact-model.md, /app/docs/geometry-rollup.md, /app/docs/tapeout-schema.md, /app/docs/spice-card.md, /app/docs/validation-schema.md, /app/docs/parameter-bounds.md, /app/docs/measurement-formats.md, /app/docs/geometry-sharing.md, and /app/docs/bundled-sample-data.md. Complete the tb3 calibration kernel under /app/tb3 in Rust, then drive calibration through /app/bin/gaa-extract after a release rebuild from /app sources via /app/scripts/build.sh.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
