# # Repair the pendulum motion solver

Submission: `bb361b7b-e01f-4068-beac-4c197355eee7`  
Slug: `repair-the-pendulum-motion-solver`  
Latest archive: `bb361b7b-e01f-4068-beac-4c197355eee7_submission_2026-07-11T15_01_05.310Z.zip`  
Revisions in Dropbox: 1

## Task summary

The `/app` pendulum imaging experiment stores short grayscale montages of a damped harmonic oscillator on a fixed capture cadence. The numerical reconstruction module is missing so natural frequency, exponential decay rate, per frame acceptance masks, and audit diagrams are absent or untrustworthy. Repair the motion solver implementation in `/app` and fix any bundled `/app/environment/pendulum_recovery` modules the numerical pipeline depends on, using `/app/README.md` and `/app/schema.sql`. Implement `recover_motion.py` to decode each montage, track the bob center, reject noised or occluded frames, and fit the damped cosine model x(t)=A*exp(-gamma*t)*cos(2*pi*f*t+phi) with nonlinear least squares. Persist fitted f and gamma, accepted angle samples, per frame audit records, and Graphviz diagrams. Hand written parameter files or graph artifacts without running the solver will not pass verification.

Required artifacts include: `/app/environment/pendulum_recovery`, `/app/README.md`, `/app/schema.sql`, `/app/environment/pendulum_recovery/report.py`.

Author anonymous tagged this **hard** scientific-computing task (numerical-methods, harmonic-oscillator, curve-fitting, scipy, simulation, image-tracking).

Time estimates: expert ~360 min, junior ~960 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `bb361b7b-e01f-4068-beac-4c197355eee7_submission_2026-07-11T15_01_05.310Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
