# Portfall is a terminal puzzle played inside a stack of shipping containers. Play

Submission: `86c0da71-3a31-46ae-9e45-dfe273ebf3f8`  
Slug: `portfall-is-a-terminal-puzzle-played-inside-a-stack-of-shipp`  
Latest archive: `86c0da71-3a31-46ae-9e45-dfe273ebf3f8_submission_2026-07-22T03_24_06.821Z.zip`  
Revisions: 1

## Task summary

Portfall is a terminal puzzle played inside a stack of shipping containers. Players submit command transcripts, and the game master needs an automated referee that applies the Portfall operations manual consistently instead of judging each game by hand. Complete the Portfall game referee exposed from `/app/src` by providing `adjudicatePortfall`, `summarizePortfallLeague`, and `writePortfallAuditPack`. The referee must replay transcript text against the supplied container layout at `/app/portfall/container-spec.example.json`, follow the puzzle rules in `/app/portfall/manual.md`, and return canonical JSON using the game-state shapes in `/app/src/types.ts`. Keep the package importable for the verifier with no standalone CLI, network calls, timestamps, randomness, or external services.

Required artifacts include: `/app/src`, `/app/portfall/container-spec.example.json`, `/app/portfall/manual.md`, `/app/src/types.ts`, `/app/transcripts`, `/app/golden/adjudications`.

Author anonymous tagged this **medium** games task (games, terminal-game, escape-room, container-puzzle, puzzle-adjudication, game-referee, scorekeeping).

Time estimates: expert ~45 min, junior ~90 min.

Harbor timeouts: agent 900s, verifier 300s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `86c0da71-3a31-46ae-9e45-dfe273ebf3f8_submission_2026-07-22T03_24_06.821Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
