# This task asks for the exact perft node count of a Chess960 (Fischer Random

Submission: `0ce31b81-1432-4620-b06e-2014f3f2575a`  
Slug: `this-task-asks-for-the-exact-perft-node-count-of-a-chess960-`  
Latest archive: `0ce31b81-1432-4620-b06e-2014f3f2575a_submission_2026-07-19T09_28_30.609Z.zip`  
Revisions in Dropbox: 1

## Task summary

This task asks for the exact perft node count of a Chess960 (Fischer Random Chess) position, where the castling rule's king/rook overlap cases are the central difficulty. A perft count at a given depth is the total number of leaf positions reachable by exactly that many consecutive plies of strictly legal play from a starting position, with every side to move choosing among all of its own legal moves at every ply.

Required artifacts include: `/app/build/chess960_perft`, `/app/data/position.txt`, `/app/output.json`.

Author anonymous tagged this **hard** games task (cpp, chess960, castling, perft, movegen).

Time estimates: expert ~75 min, junior ~270 min.

Harbor timeouts: agent 1200.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `0ce31b81-1432-4620-b06e-2014f3f2575a_submission_2026-07-19T09_28_30.609Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
