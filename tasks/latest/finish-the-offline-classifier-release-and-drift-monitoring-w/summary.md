# Finish the offline classifier release and drift-monitoring workflow exposed by `

- **UUID:** `1648bdd0-78ab-4a83-96be-3c6d58069de1`
- **Slug:** `finish-the-offline-classifier-release-and-drift-monitoring-w`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Finish the offline classifier release and drift-monitoring workflow exposed by `/app/p/wf`. The `train` and `run-drift` options, defaults, stdout contracts, input rules, release bundle, paginated product API, and Prefect names under `/app/docs/` are normative.

`train` must evaluate every configured random-forest candidate with the repeated deterministic OOF and cross-fitted sigmoid-calibration policy, select the champion with the documented six-level tie-break, refit it on all rows, and publish the exact canonical bundle in `/app/docs/model_bundle.md`. The release includes calibrated-prediction, tree-disagreement, pairwise-dependence, per-tree leaf-occupancy, and joint leaf-path sketch profiles, and identical input bytes must reproduce every bundle byte.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
