# Finish the offline classifier release and drift-monitoring workflow exposed by `

Submission: `1648bdd0-78ab-4a83-96be-3c6d58069de1`  
Slug: `finish-the-offline-classifier-release-and-drift-monitoring-w`  
Latest archive: `1648bdd0-78ab-4a83-96be-3c6d58069de1_submission_2026-07-20T02_20_22.138Z.zip`  
Revisions: 5

## Task summary

Finish the offline classifier release and drift-monitoring workflow exposed by `/app/p/wf`. The `train` and `run-drift` options, defaults, stdout contracts, input rules, release bundle, paginated product API, and Prefect names under `/app/docs/` are normative. `train` must evaluate every configured random-forest candidate with the repeated deterministic OOF and cross-fitted sigmoid-calibration policy, select the champion with the documented six-level tie-break, refit it on all rows, and publish the exact canonical bundle in `/app/docs/model_bundle.md`. The release includes calibrated-prediction, tree-disagreement, pairwise-dependence, per-tree leaf-occupancy, and joint leaf-path sketch profiles, and identical input bytes must reproduce every bundle byte.

Required artifacts include: `/app/p/wf`, `/app/docs/`, `/app/docs/model_bundle.md`, `/app/config/repro_config.json`.

Author anonymous tagged this **hard** machine-learning task (ml-ops, repeated-cross-validation, forest-uncertainty, prefect, cryptographic-integrity).

Time estimates: expert ~480 min, junior ~960 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `1648bdd0-78ab-4a83-96be-3c6d58069de1_submission_2026-07-20T02_20_22.138Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
