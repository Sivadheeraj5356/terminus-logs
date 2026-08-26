# Post-hoc probability calibration for a multi-class classifier under distribution

Submission: `5627ffa6-95f6-4c8d-90b9-806a2927fdac`  
Slug: `post-hoc-probability-calibration-for-a-multi-class-classifie`  
Latest archive: `5627ffa6-95f6-4c8d-90b9-806a2927fdac_submission_2026-07-17T17_16_00.602Z.zip`  
Revisions: 7

## Task summary

Post-hoc probability calibration for a multi-class classifier under distribution shift. Held-out inference bundles under /app/environment/data/ give raw confidences, hits, and subgroup lanes, plus a severity-ordered shift ladder with per-rung ECE budgets and strength-span limits, an optional rim used only when placing equal-mass reliability-diagram edges, and a required holdout fold used only for the emitted holdout witness. The evaluator under /app/environment must fit histogram, isotonic, and grouped-isotonic calibrators on the fit fold, measure expected calibration error (ECE) on each rung with sealed fit-plus-rim edges, and choose one calibration family per rung under budget, nondecreasing strength, and span limits. Update the calibrator sources under /app/environment so a rebuilt binary produces evaluations that meet the calibration contract on every conforming bundle, including after fold refits and interrupted evaluation runs.

Required artifacts include: `/app/environment/data/`, `/app/environment`, `/app/bin/plangen`, `/app/out/plan.json`, `/app/environment/data/bundles/steep.json`, `/app/environment/docs/model-evaluation.md`, `/app/environment/docs/public-invariants.md`, `/app/environment/docs/contract.rst`.

Author anonymous tagged this **hard** machine-learning task (probability-calibration, expected-calibration-error, isotonic-regression, distribution-shift, model-evaluation, reliability-diagrams).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `5627ffa6-95f6-4c8d-90b9-806a2927fdac_submission_2026-07-17T17_16_00.602Z.zip` is a task submission, not a Harbor job. 7 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
