# The canal transient simulator under `/app/environment` produces unstable and non

Submission: `e2b3da3e-87b1-4dae-a515-46791e9911ec`  
Slug: `the-canal-transient-simulator-under-app-environment-produces`  
Latest archive: `e2b3da3e-87b1-4dae-a515-46791e9911ec_submission_2026-07-20T07_09_27.538Z.zip`  
Revisions: 1

## Task summary

The canal transient simulator under `/app/environment` produces unstable and non-conservative results when storage geometry changes, controls occur between output times, or a run is continued from a checkpoint. Repair the C++ `lockctl` implementation so `run`, `restore`, and `audit` follow the hydraulic and numerical contracts in `/app/environment/docs` and write the requested schema-version-4 report and optional restart snapshot. The completed solver must use the documented nonlinear storage curves, hydraulic link laws, implicit midpoint/Newton method, adaptive step-doubling controller, exact event boundaries, and conservation accounting. A restored trajectory over append-only forcing must be identical to a clean trajectory over the same final inputs, while changed processed forcing or corrupt state must be rejected without changing existing outputs. `/app/environment/build/lockctl --help` must exit successfully and advertise the `run`, `restore`, and `audit` commands together with `--case`, `--output`, `--snapshot`, `--snapshot-out`, `--stop-at`, and `--ledger`. `run` accepts a case and report output plus optional stop and snapshot-output arguments, `restore` accepts a case, snapshot, and report output, and `audit` accepts a case and ledger; every path-valued argument must be absolute.

Required artifacts include: `/app/environment`, `/app/environment/docs`, `/app/environment/build/lockctl`, `/app/environment/data`.

Author anonymous tagged this **hard** scientific-computing task (nonlinear-hydraulics, implicit-integration, adaptive-timestep, checkpoint-restart, mass-conservation).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `e2b3da3e-87b1-4dae-a515-46791e9911ec_submission_2026-07-20T07_09_27.538Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
