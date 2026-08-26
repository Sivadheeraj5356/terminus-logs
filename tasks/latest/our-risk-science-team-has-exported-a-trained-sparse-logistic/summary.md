# Our risk science team has exported a trained sparse logistic model for horizon-a

- **UUID:** `d3b813bc-f88d-402c-be7e-24981a708d78`
- **Slug:** `our-risk-science-team-has-exported-a-trained-sparse-logistic`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Our risk science team has exported a trained sparse logistic model for horizon-aware fraud risk scoring. Implement the offline model inference and calibration audit routine in `/app/task_file/calibrator.py`.

The evaluator accepts exactly one argument, the task root path, consumes the trained model artifacts and binary request batch under `/app/task_file`, and emits the required model-scoring reports under `/app/task_file/output`. The complete inference semantics, trained-artifact formats, feature normalization rules, sparse observation handling, score calibration rules, monotonic post-calibration pooling rules, and audit report schemas are defined in `/app/task_file/SPEC.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
