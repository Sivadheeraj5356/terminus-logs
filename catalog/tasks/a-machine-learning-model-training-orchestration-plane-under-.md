# A machine-learning model-training orchestration plane under /app runs an offline

Submission: `f441718d-7145-4e7b-846e-e183ec2e3cc2`  
Slug: `a-machine-learning-model-training-orchestration-plane-under-`  
Latest archive: `f441718d-7145-4e7b-846e-e183ec2e3cc2_submission_2026-07-18T09_17_31.841Z.zip`  
Revisions in Dropbox: 5

## Task summary

A machine-learning model-training orchestration plane under /app runs an offline supervised training workflow for tabular feature ingest, schema normalization, feature-store sync, gradient-boosted model fitting (train), holdout evaluation (eval), artifact publish, and compliance audit. The sample AI training workflow under /app/testdata/workflows/ materializes a model-training DAG with feature, train, evaluate, and publish nodes so experiment lineage, training-checkpoint recovery, deterministic training replay, and a signed ML recovery certificate stay auditable across eight ordered machine-learning stages A→H. Stage contracts for training-workflow parsing, feature-DAG compilation, deterministic train/eval scheduling, training-checkpoint selection/merge, failed-run recovery, epoch-relative training replay, lineage verification, and HMAC recovery certification are defined under /app/docs/ (including /app/docs/ml-overview.md, /app/docs/pipeline.md, and /app/docs/stage-a.md through /app/docs/stage-h.md). Policy and the signing token live under /app/configs/. Required artifacts after a successful training run include /app/state/normalized.json, /app/state/compiled.json, /app/state/schedule.json, /app/state/execution.json, /app/state/journal.json, /app/state/checkpoints.json, /app/state/recovery.json, /app/state/recovered_checkpoint.json, /app/state/replay.json, /app/state/verification.json, /app/output/certificate.json, /app/output/certificate_status.json, /app/output/verification.json, /app/output/recovery.json, and /app/output/replay.json.

Required artifacts include: `/app/testdata/workflows/`, `/app/docs/`, `/app/docs/ml-overview.md`, `/app/docs/pipeline.md`, `/app/docs/stage-a.md`, `/app/docs/stage-h.md`, `/app/configs/`, `/app/state/normalized.json`.

Author anonymous tagged this **hard** machine-learning task (machine-learning, mlops, training-checkpoint, experiment-lineage, model-artifact, recovery-certificate).

Time estimates: expert ~600 min, junior ~1200 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `f441718d-7145-4e7b-846e-e183ec2e3cc2_submission_2026-07-18T09_17_31.841Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
