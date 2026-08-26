# Build a Go CLI binary called `tribunal-game` that simulates historical court arb

Submission: `eb439edf-c8d6-4a3c-a0d0-e38c9dcd4d8d`  
Slug: `build-a-go-cli-binary-called-tribunal-game-that-simulates-hi`  
Latest archive: `eb439edf-c8d6-4a3c-a0d0-e38c9dcd4d8d_submission_2026-07-15T16_03_14.768Z.zip`  
Revisions: 1

## Task summary

Build a Go CLI binary called `tribunal-game` that simulates historical court arbitration. Invoke it as: ``` ./tribunal-game --codex /opt/task_data/codex.txt --sessions /opt/task_data/sessions.json --seed <SCENARIO> ```

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** games task (go, games, long-context, cli, state-machine).

Time estimates: expert ~45 min, junior ~120 min.

Harbor timeouts: agent 1800.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `eb439edf-c8d6-4a3c-a0d0-e38c9dcd4d8d_submission_2026-07-15T16_03_14.768Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
