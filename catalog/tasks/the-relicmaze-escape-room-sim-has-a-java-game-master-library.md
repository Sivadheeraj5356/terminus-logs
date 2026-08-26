# The RelicMaze escape-room sim has a Java game-master library under /app/relicmaz

Submission: `873bceac-14b3-4139-b8a8-623a18e27bf3`  
Slug: `the-relicmaze-escape-room-sim-has-a-java-game-master-library`  
Latest archive: `873bceac-14b3-4139-b8a8-623a18e27bf3_submission_2026-07-06T04_33_42.289Z.zip`  
Revisions in Dropbox: 1

## Task summary

The RelicMaze escape-room sim has a Java game-master library under /app/relicmaze, and right now `com.relicmaze.Resolver` is just a stub. I need it to actually answer seekers: given a capsule and a player's transcript, `resolve()` has to replay the transcript and return the exact narration and the ordered list of next actions that a Keeper would speak. The canonical rules for all of that live in /app/relicmaze/manual/keeper-manual.md, which is the source of truth for how every line of the account is composed. The room, relic, and passage data is not in any file you can read directly; it lives in the running PostgreSQL database (see /app/relicmaze/db.properties for the connection). Query it live over JDBC. The capsules are the OCI-style image-config JSON files under /app/relicmaze/capsules, and the manual explains which of their labels and history entries the Keeper actually acts on.

Required artifacts include: `/app/relicmaze`, `/app/relicmaze/manual/keeper-manual.md`, `/app/relicmaze/db.properties`, `/app/relicmaze/capsules`, `/app/relicmaze/verifier`, `/app/relicmaze/fixtures`.

Author anonymous tagged this **hard** games task (postgresql, jdbc, escape-room, oci-image, long-context).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `873bceac-14b3-4139-b8a8-623a18e27bf3_submission_2026-07-06T04_33_42.289Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
