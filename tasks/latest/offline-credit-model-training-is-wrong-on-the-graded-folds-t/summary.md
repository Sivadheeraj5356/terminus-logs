# Offline credit-model training is wrong on the graded folds. The offline feature

- **UUID:** `303a8ae9-04ec-4794-a71e-0dcc7ce0bc3a`
- **Slug:** `offline-credit-model-training-is-wrong-on-the-graded-folds-t`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Offline credit-model training is wrong on the graded folds. The offline feature store materializes point-in-time training ledgers, then a small train and eval pass fits a model and scores holdout accuracy.

Graded folds still feed bad feature state into those training batches. Repair is required in the Go source code under /app/environment.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
