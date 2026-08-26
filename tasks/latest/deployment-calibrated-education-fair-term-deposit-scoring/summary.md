# Deployment-calibrated, education-fair term-deposit scoring

- **UUID:** `4239c3e6-6aaf-4acd-a0cd-fb9cfd0451b5`
- **Slug:** `deployment-calibrated-education-fair-term-deposit-scoring`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Deployment-calibrated, education-fair term-deposit scoring The file /app/environment/data/bank_additional.csv holds client-contact records from a bank's term-deposit campaign (UCI Bank Marketing): a stable row_id key, client and campaign attributes, five macroeconomic covariates, and y, whether the client subscribed. Rows with a present y are training data; rows with a blank y are the held-out deployment contacts to score.

The data notes describe the split and constraints.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
