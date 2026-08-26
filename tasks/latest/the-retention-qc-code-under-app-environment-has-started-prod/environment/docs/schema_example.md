# Record shape example

This fragment illustrates types only. It is not an expected result.

```json
{
  "model": {
    "training_runs": ["run-a", "run-b"],
    "centers": [{"peptide": "PEPTIDE", "center": 0.5, "support": 2}]
  },
  "replays": [{
    "holdout_run": "run-c",
    "threshold": 0.25,
    "quantile_rank": 2,
    "covered": 1,
    "total": 1
  }]
}
```

Actual output includes all sections and fields defined in `ra_contract.md`.
