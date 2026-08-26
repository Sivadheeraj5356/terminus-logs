# This is a numerical statistical-estimation task: fit a complementary log-log bin

Submission: `b33b16d3-8fdd-4081-ad26-e6da801cf111`  
Slug: `this-is-a-numerical-statistical-estimation-task-fit-a-comple`  
Latest archive: `b33b16d3-8fdd-4081-ad26-e6da801cf111_submission_2026-07-16T16_00_02.401Z.zip`  
Revisions: 2

## Task summary

This is a numerical statistical-estimation task: fit a complementary log-log binary regression by maximum likelihood on the UCI Climate Model Simulation Crashes data and report its coefficients, their inference, the model deviances and information criterion, and the average marginal effects to numerical precision. The failure outcome is rare and one sided, so the symmetric logit link is the wrong model and the complementary log-log link is the correct one, and recovering a stable fit near separation is the crux. The modelling table under /app/data, climate_crashes.csv, is one row per climate-model run: eighteen tuning-parameter columns scaled to the unit interval and a binary failure indicator that is one for a crash and zero for a completed run. Use all eighteen parameters as predictors and fit the complementary log-log binary regression by maximum likelihood, with an intercept.

Required artifacts include: `/app/data`, `/app/outputs`, `/app/contracts`, `/app/analysis.R`.

Author anonymous tagged this **medium** scientific-computing task (complementary-log-log, generalized-linear-model, maximum-likelihood-estimation, rare-event, statistical-computing).

Time estimates: expert ~40 min, junior ~140 min.

Harbor timeouts: agent 900.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `b33b16d3-8fdd-4081-ad26-e6da801cf111_submission_2026-07-16T16_00_02.401Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
