# The observatory spool worker in `/app` is producing plausible but incorrect spec

Submission: `daac4834-00ef-4f4e-825e-a151fc042820`  
Slug: `the-observatory-spool-worker-in-app-is-producing-plausible-b`  
Latest archive: `daac4834-00ef-4f4e-825e-a151fc042820_submission_2026-07-19T08_00_17.116Z.zip`  
Revisions: 3

## Task summary

The observatory spool worker in `/app` is producing plausible but incorrect spectral-drift records from bundled SPECZ frames, and interrupted runs can duplicate or skip scans. The public entry point is `/app/bin/specz-worker` (symlink to `/app/scripts/specz-worker`). Repair that AWK/Bash worker and its `/app/lib` modules so it processes valid `*.spz` files from `/data/inbox`, recovers stale work from `/data/work`, and follows the current frame, calibration, statistics, configuration, and recovery rules in `/app/docs/observatory-operations-notebook.md`, `/app/container/specz-worker.def`, and `/app/docs/operator-runbook.md`. Both documented frame revisions must remain supported. Corrupt, truncated, or conflicting inputs must be moved to `/data/quarantine` without preventing other valid scans from completing, and rerunning or resuming the worker must not duplicate or lose committed scans. Write sorted scan records to `/output/drift.jsonl`. The operator runbook documents the scan row layout with fields type, instrument, session, sequence, source_sha256, calibration_revision, sample_count, peak_centroid_nm, drift_pm, integrated_intensity, and baseline_noise. Emit worker lifecycle JSON Lines and preserve the inspect subcommand output from `/app/docs/operator-runbook.md`. Treat the notebook, Apptainer definition, bundled source frames, and operator runbook as immutable source records.

Required artifacts include: `/app/bin/specz-worker`, `/app/scripts/specz-worker`, `/app/lib`, `/app/docs/observatory-operations-notebook.md`, `/app/container/specz-worker.def`, `/app/docs/operator-runbook.md`, `/output/drift.jsonl`.

Author anonymous tagged this **hard** scientific-computing task (awk, spectroscopy, binary-protocol, checkpoint-recovery, numerical-analysis, long-context).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `daac4834-00ef-4f4e-825e-a151fc042820_submission_2026-07-19T08_00_17.116Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
