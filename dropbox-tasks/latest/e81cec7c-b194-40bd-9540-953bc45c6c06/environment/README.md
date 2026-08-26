# Scientific computing weight-conservation experiment harness (`/app`)

This is a **scientific computing** measurement stack for conserved-mass projection
estimators: scripted Monte Carlo-style cryogenic bay conservation trials, usable-capacity
fill and hold-time mass projection, absolute-MAWP and calibration gauges, specimen-placement
eligibility projection, digest-bound inventory checkpoints, and assess resume materialization.
Scientific success means inventory stages, readiness reports, and certificates agree with the
conservation laws in `/app/docs/CONTRACT.md` under checkpoint-resume — when estimators
disagree with the monolithic bay baseline, the trial is scientifically invalid. This is a
measurement-validation experiment, not a software-engineering or debugging exercise.

## Documentation

- `/app/docs/CONTRACT.md` — conserved-mass / projection-estimator conservation laws
- `/app/docs/cli-surface.md` — inventory / assess CLI
- `/app/docs/facility-schema.md` — vessels and placement requests
- `/app/docs/catalog-schema.md` — equipment models and fill/hold/MAWP formulas
- `/app/docs/maintenance-schema.md` — half-open windows
- `/app/docs/inventory-stage.md` — checkpoint fields, rounding, digests
- `/app/docs/readiness-report.md` — placement projection
- `/app/docs/certificate-contract.md` — certificate_ok gating
- `/app/docs/ledger-contract.md` — composite keys and salvage

Experiment fixtures: `/app/fixtures/`. Sources: `/app/src/` and `/app/include/cryoready/`.
After changing sources, produce an updated `/app/bin/cryoready` (see `/app/tools/build.sh`).
Reset outputs with `/app/scripts/reset_workspace.sh`.
