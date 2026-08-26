# Calibrated purchase-probability estimation under a seasonal distribution shift

- **UUID:** `6b7e03a6-1278-4c70-a23b-9c4e9b57b735`
- **Slug:** `calibrated-purchase-probability-estimation-under-a-seasonal`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Calibrated purchase-probability estimation under a seasonal distribution shift This is a supervised machine-learning task: train a probabilistic classifier on labeled browsing sessions and use it to predict calibrated purchase probabilities for unlabeled sessions that come from a different, shifted distribution. It is a domain-adaptation and probability-calibration problem, not a lookup or aggregation.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
