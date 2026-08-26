# Wellbeing program enrollment effect

This project holds employee records from a voluntary workplace wellbeing program
and asks for the average effect of enrolling on the end-of-year wellbeing index.

Start with `docs/estimand_contract.md` for exactly what to estimate,
`docs/data_dictionary.md` and `docs/variables/` for the fields, `docs/study_design.md`
for how enrollment happened, and `docs/output_schema.md` for the result format.

The data is under `data/`. Helper functions for loading and validating the joined
records are under `R/`. Write your estimator as `analysis.R` and report the result
to `/app/estimate.json`.
