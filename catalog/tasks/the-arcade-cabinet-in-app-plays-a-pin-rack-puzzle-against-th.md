# The arcade cabinet in /app plays a pin rack puzzle against the house. It is wire

Submission: `4972afae-424f-49ff-ba75-dc55991656bc`  
Slug: `the-arcade-cabinet-in-app-plays-a-pin-rack-puzzle-against-th`  
Latest archive: `4972afae-424f-49ff-ba75-dc55991656bc_submission_2026-07-17T15_42_04.446Z (1).zip`  
Revisions in Dropbox: 5

## Task summary

The arcade cabinet in /app plays a pin rack puzzle against the house. It is wired to its service link, so play it until you know how it plays. The tournament ladder racks alleys far bigger than the practice cabinet will ever set up, from a billion pins up to a trillion. It sets the ball dial and throw latch to any state, and the house never misses a winning line.

Required artifacts include: `/app/entry`, `/app/ladder`, `/app/tools`.

Author anonymous tagged this **hard** games task (combinatorial-game, arcade, black-box-play, perfect-play).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `4972afae-424f-49ff-ba75-dc55991656bc_submission_2026-07-17T15_42_04.446Z (1).zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
