# The C project at /app/environment evaluates a weighted sum of Jacobi theta

Submission: `7ccf5038-8247-4a95-824a-e84936464348`  
Slug: `the-c-project-at-app-environment-evaluates-a-weighted-sum-of`  
Latest archive: `7ccf5038-8247-4a95-824a-e84936464348_submission_2026-07-20T03_55_02.108Z.zip`  
Revisions in Dropbox: 6

## Task summary

The C project at /app/environment evaluates a weighted sum of Jacobi theta values. Each case gives N terms; term i has a coefficient c_i, an angle z_i, and a nome q_i, and the reported quantity is S = sum_{i=1}^{N} c_i * theta3(z_i, q_i),

Required artifacts include: `/app/environment`, `/app/environment/docs`, `/app/environment/src/theta.c`, `/app/environment/include/theta.h`, `/app/environment/scripts/run_all.sh`, `/app/environment/data/cases.csv`.

Author anonymous tagged this **hard** scientific-computing task (jacobi-theta, modular-transformation, catastrophic-cancellation, extended-precision, from-scratch).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1200s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `7ccf5038-8247-4a95-824a-e84936464348_submission_2026-07-20T03_55_02.108Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
