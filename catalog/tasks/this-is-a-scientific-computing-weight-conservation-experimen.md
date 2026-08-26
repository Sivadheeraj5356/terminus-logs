# This is a **scientific computing** weight-conservation experiment for conserved-

Submission: `e81cec7c-b194-40bd-9540-953bc45c6c06`  
Slug: `this-is-a-scientific-computing-weight-conservation-experimen`  
Latest archive: `e81cec7c-b194-40bd-9540-953bc45c6c06_submission_2026-07-17T05_47_21.999Z.zip`  
Revisions in Dropbox: 3

## Task summary

This is a **scientific computing** weight-conservation experiment for conserved-mass projection estimators. Under `/app`, a scientific measurement harness (`cryoready`) runs scripted Monte Carlo-style conservation trials over a cryogenic bay vessel pool, projects conserved usable-capacity fill mass, hold-time mass after reserve, absolute-MAWP pressure gauges, and specimen-placement eligibility mass onto digest-bound inventory checkpoints, then resumes assess materialization so estimator-bias diagnostics can be compared against an uninterrupted monolithic bay baseline. **Scientific computing** success means conserved fill/hold/pressure mass, maintenance-window and calibration gauges, cryogen-class compatibility estimators, preferred-placement projection estimators, certificate integrity gauges, and durable ledger continuity remain valid under checkpoint-resume — when any of those disagree with the monolithic baseline, the measurement is scientifically invalid. This is a scientific measurement-validation experiment, not a software-engineering or debugging exercise. In plain terms: every usable liter of cryogen mass that should count toward fill fraction and hold-time must still be accounted for after reserve subtraction, six-decimal rounding, absolute PSIA conversion, half-open maintenance windows, and exact-epoch sensor expiry; every specimen placement request must conserve eligibility mass onto ready compatible vessels; certificates and ledger counters must not invent or lose assess mass across truncated-file salvage. A fill projection estimator is `level_liters /...

Required artifacts include: `/app/state/inventory-stage.json`, `/app/bin/cryoready`, `/app/docs/CONTRACT.md`, `/app/docs/facility-schema.md`, `/app/docs/catalog-schema.md`, `/app/docs/maintenance-schema.md`, `/app/docs/inventory-stage.md`, `/app/docs/readiness-report.md`.

Author anonymous tagged this **medium** scientific-computing task (weight-conservation, projection-estimators, monte-carlo, checkpoint-resume, cryogenics, measurement-validation).

Time estimates: expert ~360 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `e81cec7c-b194-40bd-9540-953bc45c6c06_submission_2026-07-17T05_47_21.999Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
