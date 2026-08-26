# Our GAA nanosheet tape-out lab needs numerical device calibration closure on the

Submission: `6d680189-86a6-43d5-b2c3-604662096bb1`  
Slug: `our-gaa-nanosheet-tape-out-lab-needs-numerical-device-calibr`  
Latest archive: `6d680189-86a6-43d5-b2c3-604662096bb1_submission_2026-07-16T10_17_33.471Z (1).zip`  
Revisions: 11

## Task summary

Our GAA nanosheet tape-out lab needs numerical device calibration closure on the characterization kernel under /app before compact models can clear foundry signoff. Close the measured IV and CV sweeps against the fitted compact transistor model and publish /app/out/gaa_model.sp plus /app/out/model_validation.json from the bundled fixtures under /app/data/bundled and bounds at /app/config/parameter_bounds.toml. Normative device physics, schemas, and numeric solver rules are in /app/docs/scientific-computing-workflow.md, /app/docs/device-characterization-contract.md, /app/docs/compact-model.md, /app/docs/geometry-rollup.md, /app/docs/tapeout-schema.md, /app/docs/spice-card.md, /app/docs/validation-schema.md, /app/docs/parameter-bounds.md, /app/docs/measurement-formats.md, /app/docs/geometry-sharing.md, and /app/docs/bundled-sample-data.md. Complete the tb3 calibration kernel under /app/tb3 in Rust, then drive calibration through /app/bin/gaa-extract after a release rebuild from /app sources via /app/scripts/build.sh. Characterize builds a sealed calibration snapshot at /app/state/calibration_tapeout.json and a geometry rollup file at /app/state/geometry_rollup.json from the bundled IV and CV sweeps, geometry manifest, and contact resistance at 25.0 degrees Celsius with ordered rows and deterministic digests per /app/docs/tapeout-schema.md and /app/docs/geometry-rollup.md. Model-fit must read only that persisted calibration snapshot, geometry rollup, and /app/config/parameter_bounds.toml, fit shared and independent geometry groups with the compact-model equations and...

Required artifacts include: `/app/out/gaa_model.sp`, `/app/out/model_validation.json`, `/app/data/bundled`, `/app/config/parameter_bounds.toml`, `/app/docs/scientific-computing-workflow.md`, `/app/docs/device-characterization-contract.md`, `/app/docs/compact-model.md`, `/app/docs/geometry-rollup.md`.

Author anonymous tagged this **hard** scientific-computing task (gaa-nanosheet, compact-model, lab-calibration, numerical-simulation, device-physics, calibration-closure).

Time estimates: expert ~300 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `6d680189-86a6-43d5-b2c3-604662096bb1_submission_2026-07-16T10_17_33.471Z (1).zip` is a task submission, not a Harbor job. 11 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
