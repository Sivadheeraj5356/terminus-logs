# The leak repro is useful, but now I need the actual fix. Update the Rust host/co

Submission: `8bc16c61-0544-423b-bd92-4df63d1e26c5`  
Slug: `the-leak-repro-is-useful-but-now-i-need-the-actual-fix-updat`  
Latest archive: `8bc16c61-0544-423b-bd92-4df63d1e26c5_submission_2026-07-08T09_50_46.165Z.zip`  
Revisions: 2

## Task summary

The leak repro is useful, but now I need the actual fix. Update the Rust host/component boundary code under /app so /app/tools/run-fixed.sh cleans up transient stream-read errors instead of leaving descriptors and queued errors behind. The fixed report should go to /app/reports/fault-fixed.json and use the same report shape, SHA-256 fields, audit rows, and environment controls as the leak report, except mode should be "wasi-error-cleanup" and leaked_descriptors should be 0. Faults should still happen, fallback re-reads should preserve the packed output hash, and cleanup should handle default cadence, FAULT_EVERY, FAULT_PATTERN, STREAM_ROUNDS, and PACK_CHUNK runs without leaving queued errors behind.

Required artifacts include: `/app/tools/run-fixed.sh`, `/app/reports/fault-fixed.json`.

Author anonymous tagged this **hard** data-processing task (rust, wasi-preview2, wit-bindgen, wasmtime, resource-leak).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `8bc16c61-0544-423b-bd92-4df63d1e26c5_submission_2026-07-08T09_50_46.165Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
