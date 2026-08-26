# Evaluation database schema

Database file: `/app/data/eval.db`

## Table: `candidates`

| Column | Type | Description |
|--------|------|-------------|
| `candidate_id` | TEXT PK | Promotion candidate identifier |
| `model_id` | TEXT | Model name registered in AtlasBatch |
| `sklearn_pin` | TEXT | Required scikit-learn release tag |
| `artifact_digest` | TEXT | SHA-256 digest of the model artifact |
| `accuracy` | REAL | Holdout accuracy from eval run |
| `macro_f1` | REAL | Macro-averaged F1 from eval run |
| `latency_p99_ms` | REAL | P99 inference latency in milliseconds |
| `canary_fixture` | TEXT | Absolute path to canary JSON fixture |
| `batch_id` | TEXT | Batch identifier for waiver lookup |
| `eval_completed_at` | TEXT | ISO date when holdout evaluation finished |
| `holdout_samples` | INTEGER | Holdout row count from the evaluation run |

## Holdout sample minimum

Reject when `holdout_samples` is below **500**. See gate code `holdout_sample_insufficient` in `/app/docs/promotion-decision.schema.json`.

## Metric comparison

Round `accuracy` and `macro_f1` to three decimal places before comparing candidate values to the canary baseline. The baseline lives under `runs[]` where `profile` equals `canary`. Both rounded candidate values must be greater than or equal to the corresponding rounded baseline values.

## Canary fixture linkage

Each fixture carries a top-level `batch_id` that must match the candidate row.

## Evaluation freshness

See `/app/archives/comms/eval-window-policy.md` for the active window relative to `/app/config/eval-clock.toml`.

## Default latency ceiling

Unless an active batch-specific waiver applies, the maximum allowed `latency_p99_ms` is **45.0** ms. Waiver emails live under `/app/archives/comms/` with filenames matching `latency-waiver-*.eml`. A waiver is active only when the evaluation clock (`as_of_date`) is strictly before the revert date stated in the matching email.

## Query pattern

```sql
SELECT * FROM candidates WHERE candidate_id = ?;
```
