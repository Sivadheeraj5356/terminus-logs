# Play and win one complete Tidevault game as Gold. The vault has three rings, I, 

Submission: `903d3f30-fa3f-417d-9622-2a78cdb73a5e`  
Slug: `play-and-win-one-complete-tidevault-game-as-gold-the-vault-h`  
Latest archive: `903d3f30-fa3f-417d-9622-2a78cdb73a5e_submission_2026-07-19T06_36_26.269Z.zip`  
Revisions: 2

## Task summary

Play and win one complete Tidevault game as Gold. The vault has three rings, I, M, and O, crossed by six sectors, A through F. Gold and Violet each own three one-use pieces at each of powers one, two, and three. An action such as P2 IA M CW places a power-two piece into the empty slot IA, then rotates ring M one step; clockwise sends A to B, while counterclockwise sends A to F. After plies nine and eighteen, when the vault is half-full and full, every spoke compares the colors' total power across its three slots, and the higher total earns one cumulative point. The higher score after ply eighteen wins. The live game is exposed through /app/arena. Its status, move, transcript, and resign commands, including complete syntax and responses, are documented in /app/README.md together with the exact placement, rotation, action-order, tide-scoring, state, and legality contract. Every accepted Gold move also contains Violet's reply while the game remains ongoing, and accepted play is immutable.

Required artifacts include: `/app/arena`, `/app/README.md`.

Author anonymous tagged this **medium** games task (terminal-game, stateful-api, rotating-ring-game).

Time estimates: expert ~30 min, junior ~120 min.

Harbor timeouts: agent 1800.0s, verifier 180.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `903d3f30-fa3f-417d-9622-2a78cdb73a5e_submission_2026-07-19T06_36_26.269Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
