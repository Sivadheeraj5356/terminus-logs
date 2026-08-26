# Post-hoc probability calibration for a multi-class classifier under distribution

- **UUID:** `5627ffa6-95f6-4c8d-90b9-806a2927fdac`
- **Slug:** `post-hoc-probability-calibration-for-a-multi-class-classifie`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Post-hoc probability calibration for a multi-class classifier under distribution shift. Held-out inference bundles under /app/environment/data/ give raw confidences, hits, and subgroup lanes, plus a severity-ordered shift ladder with per-rung ECE budgets and strength-span limits, an optional rim used only when placing equal-mass reliability-diagram edges, and a required holdout fold used only for the emitted holdout witness.

The evaluator under /app/environment must fit histogram, isotonic, and grouped-isotonic calibrators on the fit fold, measure expected calibration error (ECE) on each rung with sealed fit-plus-rim edges, and choose one calibration family per rung under budget, nondecreasing strength, and span limits. Update the calibrator sources under /app/environment so a rebuilt binary produces evaluations that meet the calibration contract on every conforming bundle, including after fold refits and interrupted evaluation runs.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
