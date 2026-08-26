# Our risk science team has exported a trained sparse logistic model for horizon-a

Submission: `d3b813bc-f88d-402c-be7e-24981a708d78`  
Slug: `our-risk-science-team-has-exported-a-trained-sparse-logistic`  
Latest archive: `d3b813bc-f88d-402c-be7e-24981a708d78_submission_2026-07-18T07_18_05.328Z.zip`  
Revisions in Dropbox: 3

## Task summary

Our risk science team has exported a trained sparse logistic model for horizon-aware fraud risk scoring. Implement the offline model inference and calibration audit routine in `/app/task_file/calibrator.py`. The evaluator accepts exactly one argument, the task root path, consumes the trained model artifacts and binary request batch under `/app/task_file`, and emits the required model-scoring reports under `/app/task_file/output`. The complete inference semantics, trained-artifact formats, feature normalization rules, sparse observation handling, score calibration rules, monotonic post-calibration pooling rules, and audit report schemas are defined in `/app/task_file/SPEC.md`. In particular, preserve the bundled request batch and trained model artifacts, support duplicate and unknown feature observations exactly as specified, apply first-matching horizon windows, segment drift, pairwise feature interactions, calibration bands, post-calibration monotonic rules, probability clamping, risk labels, feature attribution traces, segment-level calibration summaries, record-level diagnostics, per-interaction contribution tracing, per-record monotonic pooling audits, global horizon reruns, single-feature ablation reruns, second-order pairwise ablation reruns, rank-corridor dominance chains, and robust policy-frontier optimization.

Required artifacts include: `/app/task_file/calibrator.py`, `/app/task_file`, `/app/task_file/output`, `/app/task_file/SPEC.md`, `/app/task_file/output/predictions.csv`, `/app/task_file/output/feature_trace.csv`, `/app/task_file/output/segment_summary.csv`, `/app/task_file/output/record_diagnostics.csv`.

Author Anonymous tagged this **hard** machine-learning task (machine-learning, logistic-regression, probability-calibration, feature-attribution, model-monitoring).

Time estimates: expert ~360.0 min, junior ~2160.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `d3b813bc-f88d-402c-be7e-24981a708d78_submission_2026-07-18T07_18_05.328Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
