# Enter the offline MLflow Maze recovery challenge in `/app/mlflow-maze`. Its YAML

Submission: `e3bb8fed-5fb2-490f-bf77-2181430d55dd`  
Slug: `enter-the-offline-mlflow-maze-recovery-challenge-in-app-mlfl`  
Latest archive: `e3bb8fed-5fb2-490f-bf77-2181430d55dd_submission_2026-07-21T22_44_27.746Z.zip`  
Revisions in Dropbox: 3

## Task summary

Enter the offline MLflow Maze recovery challenge in `/app/mlflow-maze`. Its YAML board and TOML puzzle catalog have lost rooms, exits, and prompts; competing revision chains in the MLflow-compatible SQLite tracking store contain the possible repairs. Recover one complete playable level and publish `/app/mlflow-maze/out/level-manifest.json` through the supplied game console. `/app/mlflow-maze/docs/RECOVERY_CONTRACT.md` is the authoritative rulebook for eligible runs, patch chains, global branch selection, graph validity, and command outcomes. The challenge is won only when `/app/mlflow-maze/scripts/recover-and-replay.sh` validates the canonical manifest and replays its deterministic shortest walkthrough. The manifest must retain the selected-run provenance and transcript commitment required by the supplied schema. Selection is global: a locally newer branch loses when its combined board is invalid or unsolvable, and equivalent configuration orderings or previously unseen compatible level and run identifiers must lead to the same rule-driven result.

Required artifacts include: `/app/mlflow-maze`, `/app/mlflow-maze/out/level-manifest.json`, `/app/mlflow-maze/docs/RECOVERY_CONTRACT.md`, `/app/mlflow-maze/scripts/recover-and-replay.sh`.

Author anonymous tagged this **hard** games task (mlflow, sqlite, libyaml, toml, terminal-maze, openssl).

Time estimates: expert ~300 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `e3bb8fed-5fb2-490f-bf77-2181430d55dd_submission_2026-07-21T22_44_27.746Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
