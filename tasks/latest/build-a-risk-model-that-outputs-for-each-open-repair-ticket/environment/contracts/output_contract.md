# Output contract

Write all five artifacts below into `/app/outputs`. Column names and JSON keys must match
exactly. One row of `predictions.csv` is expected for every open ticket (those whose
`repeat_visit` is blank).

## predictions.csv

One row per open ticket.

| column | meaning |
|---|---|
| `ticket_id` | the ticket identifier, exactly as it appears in the ledger |
| `repeat_probability` | your calibrated probability in `[0, 1]` that the ticket needs a repeat truck-roll |
| `dispatch_flag` | `1` to assign a senior technician now, else `0` |

## metrics.json

A single JSON object with keys `n_train, n_validation, n_test, train_positive_rate,
validation_positive_rate, roc_auc, pr_auc, recall, threshold, expected_cost, cost_fn,
cost_fp`. `cost_fn` is 5 and `cost_fp` is 1.

## cost_curve.csv

One row per candidate threshold, columns `threshold, tp, fp, tn, fn, expected_cost`.

## model_terms.csv

Columns `feature, importance`: one row per model input with a nonnegative importance,
excluding the identifier, the target, the service_month index, and any field that only
settles once the repeat outcome is known.

## fit_summary.csv

Columns `metric, value` reporting `raw_historical_rows`, `unique_tickets`, and `rows_used`:

- `raw_historical_rows` is the raw number of ledger rows in the historical periods — every
  `service_month` before the open batch — counted as exported, before any de-duplication or
  cohort filtering (so duplicate rows and `qa_audit` rows still count; the open batch does
  not).
- `unique_tickets` is the number of distinct `ticket_id` across the entire ledger (every
  `service_month`, the open batch included) after the duplicate rows are collapsed.
- `rows_used` counts the deduplicated `live` tickets — the internal `qa_audit` tickets
  dropped — that carry a `0` or `1` `repeat_visit` label; the open tickets, whose label is
  blank, are not counted.

## Quality thresholds enforced

The verifier recomputes each figure from the repaired ledger and the hidden open-ticket
repeat outcomes and holds the shipped predictions to the bounds below.

- Mean predicted repeat probability within `0.05` of the observed rate on the open batch,
  and decile calibration error (ECE) at most `0.05`.
- Within every well-represented `equipment_class` the predicted probability tracks the
  observed repeat rate within `0.08`, checked in `job_complexity` bands inside each class
  (the worst class-by-band cell), not only for the class overall. Clearing this requires
  carrying the decelerating repeat-rate trend forward correctly: fit each class's rate
  trend against `service_month` on a **saturating (log) scale** — for example the log-odds
  as a linear function of `log1p(service_month)`, or an `A*(1 - exp(-r*service_month))`
  curve — over the full labeled history and evaluate it at the open batch's later position.
  A straight-line (linear-in-period) projection overshoots the flattening rate and misses
  the band.
- The cold-start `equipment_class` (absent from every labeled row) must be **calibrated to
  its own repeat rate within `0.11`, not merely ranked**: score it with a class-agnostic
  fallback fit across all classes (for example the pooled model with the class terms
  dropped), which lands on that class's actual rate. A reference-class substitution or a
  ranking-only fill under-predicts it and fails this bound.
- Open-batch ROC AUC in the leakage-free band `[0.68, 0.88]`, and the reported validation
  `roc_auc` holds on the open batch within `0.08` (a score inflated by the post-outcome
  field collapses here).
- Recall at least `0.50`. `cost_fn = 5`, `cost_fp = 1`, and `threshold` is the
  cost-minimising row of `cost_curve.csv`.
