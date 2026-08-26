# This is a supervised machine-learning task: learn a labeling rule from labeled e

- **UUID:** `7526fd70-f095-4fa8-bbd8-a555033c4780`
- **Slug:** `this-is-a-supervised-machine-learning-task-learn-a-labeling`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

This is a supervised machine-learning task: learn a labeling rule from labeled examples and predict labels for new examples. Each instance is a directory with two files.

train.csv holds labeled training examples, one row each of four small integer features f0, f1, f2, f3 with a 0 or 1 label. test.csv holds unlabeled examples with the same four features.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
