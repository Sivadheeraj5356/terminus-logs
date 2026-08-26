# Offline training consumer

The credit-risk training job does not read raw feature packs. It consumes the
point-in-time ledger produced by materialize for each training fold.

```
python3 /app/environment/trainkit/fit_eval.py \
  --report /app/output/pit_report.json \
  --out /app/output/train_metrics.json
```

The fit path builds a tiny ridge linear model on an earlier temporal batch and
scores holdout accuracy on later samples. `leakage_hits` counts ledger rows whose
chosen revision violates the candidate / policy contract. Offline training is
only considered `training_ok` when leakage hits are zero.

Batch size is the full fold split at the midpoint by `asof_ms`. The model itself
is intentionally tiny. Correctness of the training metric rests on the feature
store materializer, not on model capacity.
