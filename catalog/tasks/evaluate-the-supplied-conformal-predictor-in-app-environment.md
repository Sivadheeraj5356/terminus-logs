# Evaluate the supplied conformal predictor in `/app/environment` across the four 

Submission: `f9831bda-e411-410b-9daa-046e8a4504f7`  
Slug: `evaluate-the-supplied-conformal-predictor-in-app-environment`  
Latest archive: `f9831bda-e411-410b-9daa-046e8a4504f7_submission_2026-07-16T06_09_09.860Z.zip`  
Revisions in Dropbox: 2

## Task summary

Evaluate the supplied conformal predictor in `/app/environment` across the four calibration profiles and all four pass modes. The evaluation must write a deterministic sixteen-cycle report to `/app/output/cp_witness.json` with the coverage and nonconformity-score consistency defined in `/app/environment/docs/cp_contract.md`. Use the existing Go evaluator and calibration fixtures. Build it with `bash /app/environment/scripts/rebuild_bins.sh`, run the evaluation with `bash /app/environment/scripts/drive_matrix.sh`, and validate the report with `/app/bin/cp_audit --coverage-audit --out /app/output/cp_witness.json`. The report must be derived from the supplied schedules and fixtures rather than replaced with a prewritten JSON file.

Required artifacts include: `/app/environment`, `/app/output/cp_witness.json`, `/app/environment/docs/cp_contract.md`, `/app/environment/scripts/rebuild_bins.sh`, `/app/environment/scripts/drive_matrix.sh`, `/app/bin/cp_audit`.

Author anonymous tagged this **hard** machine-learning task (go, conformal-prediction, uncertainty-quantification, calibration, coverage-evaluation).

Time estimates: expert ~90 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `f9831bda-e411-410b-9daa-046e8a4504f7_submission_2026-07-16T06_09_09.860Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
