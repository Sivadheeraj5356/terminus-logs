# The BookSort puzzle engine in `/app` is incomplete. Restore it as a deterministi

Submission: `d6b7eecf-e0af-4613-8f12-6bace1649909`  
Slug: `the-booksort-puzzle-engine-in-app-is-incomplete-restore-it-a`  
Latest archive: `d6b7eecf-e0af-4613-8f12-6bace1649909_submission_2026-07-19T17_11_46.442Z.zip`  
Revisions: 1

## Task summary

The BookSort puzzle engine in `/app` is incomplete. Restore it as a deterministic Go terminal game and build the finished executable at `/app/bin/booksort`. The game loads level definitions from SQLite, persists a live board, enforces legal top-book moves, and must remain reproducible across repeated runs. Players must be able to create a level, inspect the shelves, move books, undo and redo play, evaluate the win state, inspect history, request a deterministic hint, and obtain a shortest bounded solution. Advanced play also includes cryptographically checked plan execution, dependency-ordered batch execution, replay auditing, and ledger verification. These features are part of one coherent puzzle-state model: every accepted action must preserve the same movement rules, canonical ordering, digest semantics, and transactional guarantees.

Required artifacts include: `/app/bin/booksort`, `/app/schema-notes.md`, `/app/seeds/demo-levels.db`, `/app/cmd/booksort`.

Author anonymous tagged this **hard** games task (go, sqlite, dag-scheduling, transactional-integrity, graph-search, ledger-verification).

Time estimates: expert ~480 min, junior ~1200 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `d6b7eecf-e0af-4613-8f12-6bace1649909_submission_2026-07-19T17_11_46.442Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
