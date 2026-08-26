# You're in `/app`, a TOF mass spectrometry metrology bench that reconciles compet

Submission: `57f64195-039c-4caa-a97b-07976b6bc740`  
Slug: `you-re-in-app-a-tof-mass-spectrometry-metrology-bench-that-r`  
Latest archive: `57f64195-039c-4caa-a97b-07976b6bc740_submission_2026-07-21T10_33_05.458Z.zip`  
Revisions in Dropbox: 4

## Task summary

You're in `/app`, a TOF mass spectrometry metrology bench that reconciles competing flight-time calibrations into a cubic mass axis for ESI-L ladder shots. Instrument telemetry for the production shot is reachable through the local interface under `/app/instrument`. Competing bench axis candidates with correlated coefficient uncertainties are recorded under `/app/docs/lab-notes/`. Numerical evaluation runs through `/app/bin/tofmass`. The coupled cubic mass model, covariance construction and unit transforms, platform lock versus robust generalized least squares, physical monotonicity checks, full uncertainty propagation, global peak assignment, residual outlier policy, reproducibility rules, and report artifact format are defined in `/app/docs/reconcile-contract.md`. Report field requirements are in `/app/docs/report.schema.json`. Background on the TOF cubic axis criterion is in `/app/docs/tof-metrology-background.md`.

Required artifacts include: `/app/instrument`, `/app/docs/lab-notes/`, `/app/bin/tofmass`, `/app/docs/reconcile-contract.md`, `/app/docs/report.schema.json`, `/app/docs/tof-metrology-background.md`, `/app/reports/mz-axis-reconcile.json`.

Author anonymous tagged this **hard** scientific-computing task (mass-metrology, tof-axis, covariance, robust-gls, numerical-reproducibility).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `57f64195-039c-4caa-a97b-07976b6bc740_submission_2026-07-21T10_33_05.458Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
