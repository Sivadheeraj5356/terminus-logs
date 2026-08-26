# Output contract

Write two files to `/app/environment/outputs`. UTF-8, comma-delimited, header
row, no index column. Every value in metrics.json is a quoted string.

## predictions.csv

Header `row_id,pred_proba`. One row for every unscored session (every row whose
`target` is blank in the data file), sorted ascending by `row_id`.

| column | type | rule |
|---|---|---|
| `row_id` | int | the `row_id` of an unscored peak-season session |
| `pred_proba` | float | predicted probability that target = 1, in [0, 1] |

Every unscored record must appear exactly once.

## metrics.json

A flat JSON object with exactly these keys, each a quoted string.

| key | type | rule |
|---|---|---|
| `n_train` | int | number of rows with a non-blank `target` |
| `n_pilot` | int | number of labeled target-domain (pilot) rows |
| `n_test` | int | number of unscored rows |
| `n_test_low` | int | unscored rows in the low band (`ProductRelated <= 7`) |
| `n_test_med` | int | unscored rows in the med band (`8 <= ProductRelated <= 20`) |
| `n_test_high` | int | unscored rows in the high band (`ProductRelated >= 21`) |
| `roc_auc_val` | float | ROC-AUC of your model on your own validation data |
| `pr_auc_val` | float | average precision (PR-AUC) on your own validation data |
| `brier_val` | float | Brier score on your own validation data |
| `n_bands` | int | number of engagement bands handled (3) |

`n_test_low + n_test_med + n_test_high` must equal `n_test`.

## Grading

The engagement bands are low (`ProductRelated <= 7`), med (`8 <= ProductRelated
<= 20`) and high (`ProductRelated >= 21`), assigned from the data file. From
predictions.csv and the withheld labels the verifier recomputes held-out ROC-AUC,
PR-AUC and Brier score, globally and within each band, and compares them against a
reference gradient-boosted model refit on the active data file: your
discrimination must stay competitive with the reference globally and in every
band, and your Brier score must be no worse than the reference. Calibration is
checked as calibration-in-the-large: within each band, and overall, the mean
predicted probability must track the realized (held-out) purchase rate. The
reported per-band unscored counts must match the data. Every check is repeated
after the verifier re-fits and re-scores your script on several deterministic
variants of the data (including a source-composition skew and subsampled,
jittered resamples), with the reference recomputed on each variant, so the
pipeline must derive everything from the data file it reads.
