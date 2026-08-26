# You are on-call for the q7m rustc workspace under /app/environment. It replays s

Submission: `bbbd91b3-64c0-402f-885d-0cb9cd93a0cc`  
Slug: `you-are-on-call-for-the-q7m-rustc-workspace-under-app-enviro`  
Latest archive: `bbbd91b3-64c0-402f-885d-0cb9cd93a0cc_submission_2026-07-09T23_40_52.657Z.zip`  
Revisions: 2

## Task summary

You are on-call for the q7m rustc workspace under /app/environment. It replays scripted UCI move lists and writes one JSON trace row per ply. This first stage is observation only: do not repair the engine yet. Leave the Rust modules under /app/environment exactly as they are. Rebuild the workspace as it stands and rerun /app/environment/fixtures/seq_r4.pgn and /app/environment/fixtures/seq_u8.pgn through the current engine. Compare each ply outcome_code to the bundled reference adjudicator in /app/environment/docs/k9_rules.md. Write /app/output/m1_mismatch_report.json (k9-mismatch-v1; schema, counting rules, and field names in k9_rules.md). The mismatch report must be non-empty. Hand-written reports are insufficient; produce it from live engine runs. The test runner expects that on-disk report. Signal completion only after it exists.

Required artifacts include: `/app/environment`, `/app/environment/fixtures/seq_r4.pgn`, `/app/environment/fixtures/seq_u8.pgn`, `/app/environment/docs/k9_rules.md`, `/app/output/m1_mismatch_report.json`.

Author anonymous tagged this **hard** games task (rust, chess, fide, repetition, position-key, engine).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `bbbd91b3-64c0-402f-885d-0cb9cd93a0cc_submission_2026-07-09T23_40_52.657Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
