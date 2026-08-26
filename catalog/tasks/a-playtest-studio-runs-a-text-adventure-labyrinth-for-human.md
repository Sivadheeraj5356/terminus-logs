# A playtest studio runs a text-adventure labyrinth for human testers and

Submission: `fa8fdbaa-2060-4ac2-b51a-7da30a872339`  
Slug: `a-playtest-studio-runs-a-text-adventure-labyrinth-for-human`  
Latest archive: `fa8fdbaa-2060-4ac2-b51a-7da30a872339_submission_2026-07-18T19_29_41.170Z.zip`  
Revisions: 1

## Task summary

A playtest studio runs a text-adventure labyrinth for human testers and needs a hint oracle that lists every valid next action for a live session state. Sessions track room, inventory, consumed targets, and failed attempts. World geography lives in plain JSON files. Forbidden actions are embedded as @RULE lines inside each world's game-master chronicle. The working Go service at /app/bin/labyrinth-oracle already ships under /app with session creation, world loading, attempt handling, and the HTTP surface. Operators must implement the remaining playtest lanes documented under /app/docs so that probe snapshots, hint assembly, attestation digests, multi-rule chronicle parsing, inventory gates, route seals, abort tickets, and per-world chronicle resolution all match the contracts for both the bundled labyrinth world and reviewer-only worlds under /opt/verifier-fixtures/worlds.

Required artifacts include: `/app/bin/labyrinth-oracle`, `/app/docs`, `/app/docs/oracle-contract.md`, `/app/docs/world-schema.md`, `/app/docs/rules-format.md`, `/app/docs/probe-assemble-pipeline.md`, `/app/docs/snapshot-attestation.md`, `/app/docs/route-abort-contract.md`.

Author anonymous tagged this **hard** games task (labyrinth, playtest-oracle, text-adventure, go, session-hints).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `fa8fdbaa-2060-4ac2-b51a-7da30a872339_submission_2026-07-18T19_29_41.170Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
