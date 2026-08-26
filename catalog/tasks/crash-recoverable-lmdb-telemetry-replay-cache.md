# # Crash-recoverable LMDB telemetry replay cache

Submission: `46956eb6-df4f-442e-af66-72dc8af07788`  
Slug: `crash-recoverable-lmdb-telemetry-replay-cache`  
Latest archive: `46956eb6-df4f-442e-af66-72dc8af07788_submission_2026-07-07T12_49_53.643Z.zip`  
Revisions: 2

## Task summary

Repair the C telemetry replayer under `/app`. A recent persistence integration caused replay results to diverge between fresh, resumed, forced, and concurrent executions. Restore the documented behavior while preserving the native C/LMDB architecture and the existing command-line interface. The behavioral contract is distributed across the visible files under `/app/docs`. Treat those documents as authoritative and reconcile them with the implementation rather than assuming any one source file contains the complete defect. Do not modify tests, seed data, or the matrix driver. Rebuild with `bash /app/scripts/build.sh` and exercise the program through the CLI or `bash /app/scripts/run_matrix.sh`.

Required artifacts include: `/app/docs`, `/app/scripts/build.sh`, `/app/scripts/run_matrix.sh`, `/app/bin/telreplay`, `/app/state`, `/app/output/.single_report.json`.

Author anonymous tagged this **medium** data-processing task (lmdb, write-ahead-log, crash-recovery, cache-invalidation, concurrency, c).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `46956eb6-df4f-442e-af66-72dc8af07788_submission_2026-07-07T12_49_53.643Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
