# We need a small offline decoder for a CAN trace capture that came off a bench ri

Submission: `f8becc32-e9a1-4cf0-9b03-f99c5ce299b0`  
Slug: `we-need-a-small-offline-decoder-for-a-can-trace-capture-that`  
Latest archive: `f8becc32-e9a1-4cf0-9b03-f99c5ce299b0_submission_2026-07-08T15_05_25.280Z.zip`  
Revisions: 2

## Task summary

We need a small offline decoder for a CAN trace capture that came off a bench rig. Build a Go CLI at `/app/cantrace` that reads the network description and binary trace, applies the validation rules in `/app/task_file/cantrace-format.md`, and writes the JSON report. Running `/app/cantrace` with no arguments must read `/app/task_file/network.json` and `/app/task_file/public_trace.bin`, then write `/app/out/report.json`. Running `/app/cantrace <network.json> <trace.bin> <report.json>` must do the same job for another compatible capture. The verifier uses exact JSON values after parsing, so field names, lowercase reason strings, null values, ordering, and numeric values need to match the spec exactly.

Required artifacts include: `/app/cantrace`, `/app/task_file/cantrace-format.md`, `/app/task_file/network.json`, `/app/task_file/public_trace.bin`, `/app/out/report.json`.

Author Anonymous tagged this **hard** data-processing task (can-bus, binary-decoding, telemetry, validation, go).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `f8becc32-e9a1-4cf0-9b03-f99c5ce299b0_submission_2026-07-08T15_05_25.280Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
