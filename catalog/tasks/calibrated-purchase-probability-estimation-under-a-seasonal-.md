# Calibrated purchase-probability estimation under a seasonal distribution shift

Submission: `6b7e03a6-1278-4c70-a23b-9c4e9b57b735`  
Slug: `calibrated-purchase-probability-estimation-under-a-seasonal-`  
Latest archive: `6b7e03a6-1278-4c70-a23b-9c4e9b57b735_submission_2026-07-20T20_23_52.977Z.zip`  
Revisions in Dropbox: 2

## Task summary

Calibrated purchase-probability estimation under a seasonal distribution shift This is a supervised machine-learning task: train a probabilistic classifier on labeled browsing sessions and use it to predict calibrated purchase probabilities for unlabeled sessions that come from a different, shifted distribution. It is a domain-adaptation and probability-calibration problem, not a lookup or aggregation.

Required artifacts include: `/app/environment/data/online_shoppers.csv`, `/app/environment/analysis.R`, `/app/environment/contracts/output_contract.md`.

Author anonymous tagged this **hard** machine-learning task (r, classification, distribution-shift, calibration, domain-adaptation, online-retail).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1200s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `6b7e03a6-1278-4c70-a23b-9c4e9b57b735_submission_2026-07-20T20_23_52.977Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
