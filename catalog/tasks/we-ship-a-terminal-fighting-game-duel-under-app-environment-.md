# We ship a terminal fighting-game duel under `/app/environment`: two fighters on 

Submission: `c0571e0c-06e6-4501-8833-59af324838d6`  
Slug: `we-ship-a-terminal-fighting-game-duel-under-app-environment-`  
Latest archive: `c0571e0c-06e6-4501-8833-59af324838d6_submission_2026-07-18T09_57_12.244Z.zip`  
Revisions in Dropbox: 2

## Task summary

We ship a terminal fighting-game duel under `/app/environment`: two fighters on a line, integer tick physics, and online match play where the opponent's inputs arrive a few frames late. Complete the movement and combat simulation plus the predicting match client so every competitive tape stays bit-identical between the authoritative host and the online client. Build and run:

Required artifacts include: `/app/environment`, `/app/environment/scripts/build_all.sh`, `/app/environment/bin/duel`, `/app/output/duel_report.json`, `/app/environment/tapes`, `/app/environment/docs/duel_rules.md`, `/app/environment/docs/session_semantics.md`, `/app/environment/docs/traces/`.

Author anonymous tagged this **hard** games task (fighting-game, rollback-netcode, game-engine, determinism, rust).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `c0571e0c-06e6-4501-8833-59af324838d6_submission_2026-07-18T09_57_12.244Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
