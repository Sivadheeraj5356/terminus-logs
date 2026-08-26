# Output contract

This is a supervised machine-learning task combining a case-control label shift with
an education-fairness constraint. The training rows are enriched — subscribers kept,
non-subscribers down-sampled — so the training subscription rate is about one half,
far above the true deployment rate. Train a model, recover the deployment rate from
the unlabelled held-out contacts, and reconcile your scores onto it so they are
calibrated within every education group.

`education` is a protected attribute and must not be a model input, directly or
through a one-to-one recoding of it. Every other column may be used. The verifier
reruns the script on a variant in which only the education column has been permuted;
predictions and metrics must be unchanged.

Write two files to `/app/environment/outputs`. UTF-8, comma-delimited, header row, no
index column. Every value in metrics.json is a quoted string.

## predictions.csv

Header `row_id,pred_proba`. One row for every held-out contact (every row whose `y`
is blank), sorted ascending by `row_id`. `pred_proba` is the deployment probability of
subscription in [0, 1], 6 decimals. Every held-out contact appears exactly once.

## metrics.json

A flat JSON object with exactly these keys, each a quoted string: `n_train`,
`n_test`, `roc_auc_val`, `pr_auc_val`, `brier_val` (your model's own validation
metrics), and `n_subgroups` (distinct education values in the full data file).

## Grading

A subgroup is graded when it has at least 300 held-out contacts and at least 15
held-out subscribers. The verifier recomputes held-out ROC-AUC, PR-AUC and Brier
globally and within every graded subgroup, against an **unaware** reference
gradient-boosted model (blind to education) that recovers the deployment rate from
the unlabelled held-out contacts by black-box shift estimation and reconciles onto it.

A valid solution keeps global ROC-AUC no more than 0.025 below the reference, global
PR-AUC no more than 0.045 below it, and global Brier no more than 10 percent above it.
Within every graded subgroup it keeps ROC-AUC no more than 0.055 below the reference's
subgroup ROC-AUC, Brier no more than 15 percent above it, and — the crux — a
calibration gap (the absolute difference between the subgroup's mean prediction and
its true deployment subscription rate) no more than 0.025 above the reference's own
gap for that subgroup. The disparity certificate bounds the worst subgroup gap and
the cross-subgroup spread of ROC-AUC and Brier against the reference.

A model left at the enriched training rate has a mean prediction near one half and a
per-subgroup calibration gap of roughly 0.3, and fails. A further rerun on a
deterministically subsampled and jittered variant repeats every check against a
reference recomputed on that variant.
