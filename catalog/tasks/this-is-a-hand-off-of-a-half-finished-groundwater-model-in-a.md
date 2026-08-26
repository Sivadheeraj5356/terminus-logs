# This is a hand-off of a half-finished groundwater model in `/app`. The site setu

Submission: `fa7188e0-c8ed-4560-928a-b504057dcb16`  
Slug: `this-is-a-hand-off-of-a-half-finished-groundwater-model-in-a`  
Latest archive: `fa7188e0-c8ed-4560-928a-b504057dcb16_submission_2026-07-06T22_58_02.125Z.zip`  
Revisions in Dropbox: 1

## Task summary

This is a hand-off of a half-finished groundwater model in `/app`. The site setup is in `/app/site_config.json`, and `/app/model_notes.md` defines the transport physics, numerical behavior, sampling rules, well interpolation, and output details. The current transport and sampling modules are stubbed, so the reported risk numbers are not usable. Implement the reusable JavaScript logic in `/app/simulate.js`, `/app/step_transport.js`, and `/app/sample_aquifer_params.js`. `/app/run_risk_study.js` should remain the Node driver that imports and calls those modules for the baseline case and the seeded Monte Carlo study. The final simulation should match the transport behavior described in `/app/model_notes.md`: downgradient plume movement, flow-oriented spreading, sorption slowdown, attenuation, zero-gradient edge behavior, and continuous source release. Keep final grids finite, nonnegative apart from rounding noise, bounded by `source_conc` apart from rounding noise, and physically sensible. Do not hard-code expected output values or bypass the final simulation grid: every reported baseline and Monte Carlo well concentration must be bilinear interpolation from that run's final grid.

Required artifacts include: `/app/site_config.json`, `/app/model_notes.md`, `/app/simulate.js`, `/app/step_transport.js`, `/app/sample_aquifer_params.js`, `/app/run_risk_study.js`, `/app/output/baseline_final.csv`, `/app/output/risk_summary.json`.

Author anonymous tagged this **hard** scientific-computing task (javascript, nodejs, monte-carlo, pde, numerical-computing, groundwater).

Time estimates: expert ~75 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `fa7188e0-c8ed-4560-928a-b504057dcb16_submission_2026-07-06T22_58_02.125Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
