# # Cross-conformal p-values for forest cover-type mapping

- **UUID:** `a0dbbb54-d9e2-47eb-9e91-e8433220be33`
- **Slug:** `cross-conformal-p-values-for-forest-cover-type-mapping`
- **Category:** machine-learning
- **Difficulty:** medium

## Summary

A land-survey program classifies terrain cells into seven forest cover types. For a batch of unlabelled evaluation cells you must compute, from fixed nonconformity scores and a K-fold partition of the labelled cells, **cross-conformal p-values** for every candidate cover type, combine them across folds with the requested validity-preserving rule, and assemble label sets — implementing the exact finite-sample procedure below.

All graded arithmetic is exact rational arithmetic; every reported number is a reduced fraction. Write a base-R program at `/app/environment/analysis.R`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
