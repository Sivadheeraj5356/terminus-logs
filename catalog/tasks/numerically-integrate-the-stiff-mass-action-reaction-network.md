# Numerically integrate the stiff mass-action reaction networks that the Halvard k

Submission: `53b0bd56-418d-4b64-abb6-10d4248104fc`  
Slug: `numerically-integrate-the-stiff-mass-action-reaction-network`  
Latest archive: `53b0bd56-418d-4b64-abb6-10d4248104fc_submission_2026-07-18T06_20_39.640Z.zip`  
Revisions: 2

## Task summary

Numerically integrate the stiff mass-action reaction networks that the Halvard kinetics bench certifies. Each network file names its species, its elementary reactions and rate constants, its initial concentrations, its horizon and its error tolerances. The bench at /app/bench/bench still integrates the twelve calibration systems compiled into it; /app/calibration holds those same twelve as files. Uncertified assay networks sit in /app/assay.

Required artifacts include: `/app/bench/bench`, `/app/calibration`, `/app/assay`, `/app/bin/integrate`.

Author anonymous tagged this **hard** scientific-computing task (ode-integration, reaction-kinetics, numerical-analysis).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 720.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `53b0bd56-418d-4b64-abb6-10d4248104fc_submission_2026-07-18T06_20_39.640Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
