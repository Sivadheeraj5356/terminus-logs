# concurrency_ordering

Submission: `2c6899dd-c790-45f7-80f4-bdb3903e2958`  
Slug: `concurrency-ordering`  
Latest archive: `2c6899dd-c790-45f7-80f4-bdb3903e2958_submission_2026-07-16T04_05_18.070Z.zip`  
Revisions in Dropbox: 1

## Task summary

Wrap seats on the hex lobby disagree with their flat controls for the same seed. A wrapped control seat should agree with its flat reference on final_counts, history_len, rejected_repeats, position_digests, and terminal_digest for the same seed and interior stone sequence. Longer exchanges can leave material that should already be gone, and a saved journal can admit a repeat the live lobby would reject while still blocking some legal non-repeating moves. Repair sources under `/app` so a release rebuild of `/app/target/release/arena_cli` writes `/app/output/runs/<scenario_id>.json` from those sources. Workspace library modules behind that binary must behave correctly, not only the console wiring. Keep the existing CLI layout and run record format. Parent directories under `/app/output/runs` must exist before any write lands; create them if they are missing (mkdir is fine).

Required artifacts include: `/app/target/release/arena_cli`, `/app/output/runs/`, `/app/output/runs`, `/app/docs/cli.md`, `/app/docs/trace.md`.

Author anonymous tagged this **hard** games task (terminal-game, hex-grid, toroidal-topology, capture-rules, state-replay, rust).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `2c6899dd-c790-45f7-80f4-bdb3903e2958_submission_2026-07-16T04_05_18.070Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
