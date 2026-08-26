# The C project at /app/environment evaluates, per case, the weighted sum

Submission: `dadc5d8b-258c-4141-8a23-e519f93ab351`  
Slug: `the-c-project-at-app-environment-evaluates-per-case-the-weig`  
Latest archive: `dadc5d8b-258c-4141-8a23-e519f93ab351_submission_2026-07-09T15_54_01.560Z.zip`  
Revisions: 1

## Task summary

The C project at /app/environment evaluates, per case, the weighted sum S = sum_i c_i * erf(x_i)

Required artifacts include: `/app/environment`, `/app/environment/src/erfsum.c`, `/app/environment/include/erfsum.h`, `/app/environment/scripts/run_all.sh`, `/app/environment/data/cases.csv`, `/app/environment/outputs/`, `/app/environment/docs/format.md`.

Author anonymous tagged this **hard** scientific-computing task (special-functions, error-function, catastrophic-cancellation, extended-precision, weighted-sum, numerical-stability).

Time estimates: expert ~90 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `dadc5d8b-258c-4141-8a23-e519f93ab351_submission_2026-07-09T15_54_01.560Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
