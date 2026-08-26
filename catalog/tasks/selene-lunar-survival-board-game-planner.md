# # Selene lunar survival board-game planner

Submission: `0ab515ca-056e-4b9d-8279-6dbe5bf55577`  
Slug: `selene-lunar-survival-board-game-planner`  
Latest archive: `0ab515ca-056e-4b9d-8279-6dbe5bf55577_submission_2026-07-21T04_39_52.072Z.zip`  
Revisions: 9

## Task summary

Write the player bot for Selene, a deterministic turn-based lunar colony survival board game. Each sol is one game turn: choose the crew's ration policy and colony action, resolve the published hazard for that turn, satisfy the end-of-campaign charter, and emit the winning game replay with its resource ledger. The required Go entry point is `/workspace/task_file/main.go`. It is run from `/workspace` with:

Required artifacts include: not named as `/app` paths.

Author Anonymous tagged this **hard** games task (turn-based-game, survival-game, lunar-colony, campaign-replay, go).

Time estimates: expert ~360.0 min, junior ~1080.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `0ab515ca-056e-4b9d-8279-6dbe5bf55577_submission_2026-07-21T04_39_52.072Z.zip` is a task submission, not a Harbor job. 9 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
