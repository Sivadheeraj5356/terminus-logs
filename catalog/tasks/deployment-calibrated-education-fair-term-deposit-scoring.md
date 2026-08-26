# Deployment-calibrated, education-fair term-deposit scoring

Submission: `4239c3e6-6aaf-4acd-a0cd-fb9cfd0451b5`  
Slug: `deployment-calibrated-education-fair-term-deposit-scoring`  
Latest archive: `4239c3e6-6aaf-4acd-a0cd-fb9cfd0451b5_submission_2026-07-18T04_30_15.176Z.zip`  
Revisions in Dropbox: 1

## Task summary

Deployment-calibrated, education-fair term-deposit scoring The file /app/environment/data/bank_additional.csv holds client-contact records from a bank's term-deposit campaign (UCI Bank Marketing): a stable row_id key, client and campaign attributes, five macroeconomic covariates, and y, whether the client subscribed. Rows with a present y are training data; rows with a blank y are the held-out deployment contacts to score. The data notes describe the split and constraints.

Required artifacts include: `/app/environment/data/bank_additional.csv`, `/app/environment/analysis.R`, `/app/environment/outputs/predictions.csv`, `/app/environment/contracts/output_contract.md`.

Author anonymous tagged this **hard** machine-learning task (r, classification, fairness, case-control, label-shift, calibration, uci).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1200s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `4239c3e6-6aaf-4acd-a0cd-fb9cfd0451b5_submission_2026-07-18T04_30_15.176Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
