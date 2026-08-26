# Repair the `fusion` binary in `/app/cmd/fusion` to implement the contract in `/a

Submission: `faee0d15-8a98-4b88-8538-d03b625f3af7`  
Slug: `repair-the-fusion-binary-in-app-cmd-fusion-to-implement-the`  
Latest archive: `faee0d15-8a98-4b88-8538-d03b625f3af7_submission_2026-07-06T12_07_02.699Z.zip`  
Revisions: 2

## Task summary

Repair the `fusion` binary in `/app/cmd/fusion` to implement the contract in `/app/docs/auroral-lattice-contract.md`. The repaired binary must support this invocation: `fusion --telemetry-dir /app/telemetry --calibration-dir /app/calibration --probe /app/probe/driftprobe --probe-batch /app/telemetry/public.cfr --out /app/output/events.tsv --audit-out /app/output/audit.json`

Required artifacts include: `/app/cmd/fusion`, `/app/docs/auroral-lattice-contract.md`, `/app/telemetry`, `/app/calibration`, `/app/probe/driftprobe`, `/app/telemetry/public.cfr`, `/app/output/events.tsv`, `/app/output/audit.json`.

Author anonymous tagged this **hard** data-processing task (go, binary-format, telemetry, calibration, fixed-point, encoding).

Time estimates: expert ~360 min, junior ~1400 min.

Harbor timeouts: agent 1800s, verifier 420s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `faee0d15-8a98-4b88-8538-d03b625f3af7_submission_2026-07-06T12_07_02.699Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
