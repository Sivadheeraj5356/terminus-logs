# A machine-learning model-training orchestration plane under /app runs an offline

- **UUID:** `f441718d-7145-4e7b-846e-e183ec2e3cc2`
- **Slug:** `a-machine-learning-model-training-orchestration-plane-under`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

A machine-learning model-training orchestration plane under /app runs an offline supervised training workflow for tabular feature ingest, schema normalization, feature-store sync, gradient-boosted model fitting (train), holdout evaluation (eval), artifact publish, and compliance audit. The sample AI training workflow under /app/testdata/workflows/ materializes a model-training DAG with feature, train, evaluate, and publish nodes so experiment lineage, training-checkpoint recovery, deterministic training replay, and a signed ML recovery certificate stay auditable across eight ordered machine-learning stages A→H.

Stage contracts for training-workflow parsing, feature-DAG compilation, deterministic train/eval scheduling, training-checkpoint selection/merge, failed-run recovery, epoch-relative training replay, lineage verification, and HMAC recovery certification are defined under /app/docs/ (including /app/docs/ml-overview.md, /app/docs/pipeline.md, and /app/docs/stage-a.md through /app/docs/stage-h.md). Policy and the signing token live under /app/configs/.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
