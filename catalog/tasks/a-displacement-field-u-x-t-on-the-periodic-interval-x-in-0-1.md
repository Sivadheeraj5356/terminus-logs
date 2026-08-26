# A displacement field u(x, t) on the periodic interval x in [0, 1) obeys the damp

Submission: `f0d52f86-7534-43e8-8e2c-b3f3b73212b2`  
Slug: `a-displacement-field-u-x-t-on-the-periodic-interval-x-in-0-1`  
Latest archive: `f0d52f86-7534-43e8-8e2c-b3f3b73212b2_submission_2026-07-19T07_44_08.181Z.zip`  
Revisions in Dropbox: 3

## Task summary

A displacement field u(x, t) on the periodic interval x in [0, 1) obeys the damped wave equation u_tt + 2 g u_t = c squared times u_xx, with positive wave speed c and positive damping g. The interval wraps and the field starts from rest, so its initial time derivative is zero. A C project in /app supplies the driver, parser, grid, profile sampling, and CSV writer, leaving only the time integrator. Implement scheme_advance, declared in /app/include/scheme.h and stubbed in /app/src/scheme.c, advancing the state in place between successive times. The state has length two N: the displacement in the first N entries and its derivative u_t in the next N, on the grid x_i = i/N. Build with make in /app, then run /app/solver /app/input/transport.json /app/output/field.csv, which writes rows t,x,u,v per snapshot time and grid point in increasing x. The input gives c, g, N, a Courant number nu, the final and snapshot times, and the initial profile.

Required artifacts include: `/app/include/scheme.h`, `/app/src/scheme.c`, `/app/solver`, `/app/input/transport.json`, `/app/output/field.csv`.

Author anonymous tagged this **unknown** scientific-computing task (telegraph-equation, finite-difference, numerical-analysis, high-order-scheme, hyperbolic-pde, convergence-order).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 900s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `f0d52f86-7534-43e8-8e2c-b3f3b73212b2_submission_2026-07-19T07_44_08.181Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
