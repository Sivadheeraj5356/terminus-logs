# The Rust project in `/app` builds a binary called `cryoctl` that maintains a

Submission: `4fa720b2-0e19-4206-a330-73e7a27d1078`  
Slug: `the-rust-project-in-app-builds-a-binary-called-cryoctl-that`  
Latest archive: `4fa720b2-0e19-4206-a330-73e7a27d1078_submission_2026-07-08T04_02_37.109Z.zip`  
Revisions: 2

## Task summary

The Rust project in `/app` builds a binary called `cryoctl` that maintains a per-cryostat boil-off warden for a bank of cryogenic helium storage vessels. It reads a single JSON object from stdin describing a grace allowance and a stream of timestamped events — cryostats crossing above and below their relief threshold, transfer-line purge windows, and reports — replays them in order against a continuous-time monitor, and writes one JSON object to stdout with an `audit` trail, the closed `boiloff` intervals, and per-cryostat exposed aggregates. The current build handles the common case — a cryostat that dwells above its relief threshold past the grace allowance and then settles — but mishandles how the boil-off accrual interacts with transfer-line purge windows and with at-risk stretches that cross the allowance between events, so some boil-off intervals and exposed totals come out wrong. Fix the implementation so every case matches the specification.

Required artifacts include: `/app/docs/spec.md`, `/app/build.sh`, `/app/cryoctl`.

Author anonymous tagged this **hard** scientific-computing task (cryogenics, boil-off-monitor, grace-allowance, interval-computation, continuous-time-simulation).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `4fa720b2-0e19-4206-a330-73e7a27d1078_submission_2026-07-08T04_02_37.109Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
