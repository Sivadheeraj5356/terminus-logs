# # Competing-risks progression modelling for a monoclonal-gammopathy cohort

- **UUID:** `23e625d3-d02a-4d75-8e50-4d1ea8240ec4`
- **Slug:** `competing-risks-progression-modelling-for-a-monoclonal-gammo`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

You are handed an event-history registry for a monoclonal-gammopathy (MGUS) cohort followed for progression to plasma-cell malignancy (PCM) and for death. PCM and death compete: a patient who dies first can never progress, so any analysis that treats death as ordinary censoring overstates PCM risk.

The CSV is already a clean numerical registry — no cleaning, joining, or ETL is needed. Working in `/app`, write `/app/analysis.R` (base R only — no add-on survival package is installed) that reads `/app/data/registry.csv` and `/app/config/analysis.csv`, then writes three files under `OUTPUT_PATH` (default `/app/outputs`): `estimands.csv`, `prediction_spec.csv`, `predictions.csv`, and `cohort_summary.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
