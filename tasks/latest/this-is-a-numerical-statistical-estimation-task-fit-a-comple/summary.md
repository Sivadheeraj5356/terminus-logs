# This is a numerical statistical-estimation task: fit a complementary log-log bin

- **UUID:** `b33b16d3-8fdd-4081-ad26-e6da801cf111`
- **Slug:** `this-is-a-numerical-statistical-estimation-task-fit-a-comple`
- **Category:** scientific-computing
- **Difficulty:** medium

## Summary

This is a numerical statistical-estimation task: fit a complementary log-log binary regression by maximum likelihood on the UCI Climate Model Simulation Crashes data and report its coefficients, their inference, the model deviances and information criterion, and the average marginal effects to numerical precision. The failure outcome is rare and one sided, so the symmetric logit link is the wrong model and the complementary log-log link is the correct one, and recovering a stable fit near separation is the crux.

The modelling table under /app/data, climate_crashes.csv, is one row per climate-model run: eighteen tuning-parameter columns scaled to the unit interval and a binary failure indicator that is one for a crash and zero for a completed run. Use all eighteen parameters as predictors and fit the complementary log-log binary regression by maximum likelihood, with an intercept.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
