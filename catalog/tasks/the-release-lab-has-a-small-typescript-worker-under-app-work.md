# The release lab has a small TypeScript worker under `/app/worker` that should tu

Submission: `31078c0e-46e8-4ae1-a5f8-34c93862d360`  
Slug: `the-release-lab-has-a-small-typescript-worker-under-app-work`  
Latest archive: `31078c0e-46e8-4ae1-a5f8-34c93862d360_submission_2026-07-09T15_05_03.705Z.zip`  
Revisions: 2

## Task summary

The release lab has a small TypeScript worker under `/app/worker` that should turn a directory of OCI-style diffusion experiment cards into a deterministic Monte Carlo reduction report. Make the source under `/app/worker` regenerate the report through the normal command; a manual or static JSON write is not sufficient because the verifier reruns the command on the default fixtures and on additional valid input directories. Please make this command work: `cd /app/worker && npm run report -- --spec-dir /app/worker/fixtures/specs --calibration /app/worker/fixtures/calibrations.json --output /app/output/diffusion-report.json`

Required artifacts include: `/app/worker`, `/app/worker/fixtures/specs`, `/app/worker/fixtures/calibrations.json`, `/app/output/diffusion-report.json`.

Author anonymous tagged this **hard** scientific-computing task (monte-carlo, simulation, typescript, yaml, deterministic, validation).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 900s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `31078c0e-46e8-4ae1-a5f8-34c93862d360_submission_2026-07-09T15_05_03.705Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
