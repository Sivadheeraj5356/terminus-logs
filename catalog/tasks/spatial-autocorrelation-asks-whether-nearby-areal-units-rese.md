# Spatial autocorrelation asks whether nearby areal units resemble one another mor

Submission: `207f76a5-b1a3-4cff-95fe-a4ec28a94a3e`  
Slug: `spatial-autocorrelation-asks-whether-nearby-areal-units-rese`  
Latest archive: `207f76a5-b1a3-4cff-95fe-a4ec28a94a3e_submission_2026-07-18T09_42_15.478Z.zip`  
Revisions in Dropbox: 1

## Task summary

Spatial autocorrelation asks whether nearby areal units resemble one another more than chance allows. Here a map of U.S. counties carries two attributes (a binary label, black (1) or white (0), and an integer numeric value) together with a disclosed binary contiguity edge list that defines the first-order neighbour matrix W1. We want three classic diagnostics computed exactly and read off the same weight geometry, so that the neighbour structure is shared and any error in it propagates. For the binary label we want the Cliff-Ord weight sums S0, S1 and S2, the observed black-black, white-white and black-white boundary counts under the undirected half-edge convention, and, under both the free-sampling null (each unit independently black with probability n1/n) and the nonfree conditional null (the count of black units held fixed), the exact expectation, variance and a two-sided verdict for each join count. Under that conditional null we also want the exact two-sided permutation p-value of each join count, obtained by enumerating the equally likely labellings whenever their number is small enough to enumerate. For the numeric value we want Moran's I and Geary's C with their exact randomization expectation and variance (the Cliff-Ord moments that carry the sample kurtosis b2) and a two-sided verdict.

Required artifacts include: `/app/join_count.R`, `/app/data`, `/app/docs/SCHEMA.md`, `/app/docs/OUTPUT-CONTRACT.md`.

Author anonymous tagged this **hard** scientific-computing task (spatial-statistics, spatial-autocorrelation, join-count, morans-i, gearys-c, areal-data, contiguity, cliff-ord, exact-arithmetic, free-and-nonfree-sampling, second-order-contiguity, row-standardized-weights).

Time estimates: expert ~210 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `207f76a5-b1a3-4cff-95fe-a4ec28a94a3e_submission_2026-07-18T09_42_15.478Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
