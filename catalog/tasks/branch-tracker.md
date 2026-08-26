# # Branch tracker

Submission: `11e7ddd8-15da-4ffa-9d27-01149a2cfee3`  
Slug: `branch-tracker`  
Latest archive: `11e7ddd8-15da-4ffa-9d27-01149a2cfee3_submission_2026-07-15T11_14_06.308Z.zip`  
Revisions in Dropbox: 1

## Task summary

Implement `trace_branch` in `/app/environment/src/continuation.cpp`. It is currently a stub that returns nothing. Two discretised boundary-value problems, each carrying a parameter `lambda`, are fully specified in `/app/environment/docs/problem.md`. Each one's solution set is a curve in `R^16`. Given a problem name, a branch selector `k`, and a list of arclengths, `trace_branch` must return the point of the specified branch at each requested arclength, measured along that branch from its start.

Required artifacts include: `/app/environment/src/continuation.cpp`, `/app/environment/docs/problem.md`, `/app/environment/src/main.cpp`, `/app/environment`.

Author anonymous tagged this **unknown** scientific-computing task (numerical-continuation, nonlinear-solve, bifurcation, branch-switching, arclength-parametrisation, singular-jacobian).

Time estimates: expert ~150 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `11e7ddd8-15da-4ffa-9d27-01149a2cfee3_submission_2026-07-15T11_14_06.308Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
