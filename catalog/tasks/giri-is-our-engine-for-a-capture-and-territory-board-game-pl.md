# giri is our engine for a capture-and-territory board game played on an arbitrary

Submission: `0435f10d-6622-40c5-af14-cbf3d0aa9690`  
Slug: `giri-is-our-engine-for-a-capture-and-territory-board-game-pl`  
Latest archive: `0435f10d-6622-40c5-af14-cbf3d0aa9690_submission_2026-07-20T07_05_40.874Z.zip`  
Revisions in Dropbox: 1

## Task summary

giri is our engine for a capture-and-territory board game played on an arbitrary graph board, and the rules core still needs to be written. The board's intersections and their adjacencies are in /app/board.spec, and the recorded games are the move logs under /app/games. The rules — groups and liberties, how captures resolve, when a move is suicide, the repetition rule, passing and how a game ends, and area scoring — are written up in /app/docs/RULES.md; the move-log grammar is in /app/docs/NOTATION.md; the results schema, the group-graph format, and the command-line interface are in /app/docs/STORE.md. The Rust crate under /app already has the command-line entry point and the notation parser; the board model, the capture and legality logic, the repetition check, scoring, the results store, and the graph output are stubbed out. There is no network here, so keep the crate dependency-free and reach SQLite and Graphviz through the sqlite3 and dot binaries that are already installed. giri replay should replay every recorded game under /app/games, determine the index of the first illegal move if there is one, reconstruct the final position, compute each player's area score and capture counts, and write the results for every game into the SQLite database named by --db. giri graph --game <id> should emit that game's final group-and-region graph as Graphviz and render it to SVG with dot. giri report should print a game's stored result. Replaying the same games twice must produce identical results. Build the release binary at /app/target/release/giri.

Required artifacts include: `/app/board.spec`, `/app/games`, `/app/docs/RULES.md`, `/app/docs/NOTATION.md`, `/app/docs/STORE.md`, `/app/target/release/giri`.

Author anonymous tagged this **hard** games task (rust, graphviz, sqlite, game-engine, replay).

Time estimates: expert ~110 min, junior ~300 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `0435f10d-6622-40c5-af14-cbf3d0aa9690_submission_2026-07-20T07_05_40.874Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
