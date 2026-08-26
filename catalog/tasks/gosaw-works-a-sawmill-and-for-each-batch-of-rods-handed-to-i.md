# gosaw works a sawmill and, for each batch of rods handed to it, says who is winn

Submission: `cb84d31f-de2f-4367-bbef-14b2bb8a827b`  
Slug: `gosaw-works-a-sawmill-and-for-each-batch-of-rods-handed-to-i`  
Latest archive: `cb84d31f-de2f-4367-bbef-14b2bb8a827b_submission_2026-07-21T09_48_30.858Z.zip`  
Revisions in Dropbox: 8

## Task summary

gosaw works a sawmill and, for each batch of rods handed to it, says who is winning. A rod is a whole number of units of timber long. A turn is one cut: a player takes a single rod and saws it across into two rods, each one unit or more. The two players take turns, and the player who makes the last cut wins, so the player faced with a row too short to saw has lost. How much a cut costs depends on the row. A rod of nought units is an empty place, a gap, that holds its spot but can never be sawn. The gaps set the blade for the whole batch. When the row holds an even number of gaps, or none, the blade runs heavy and eats one unit of timber at each cut, so the two rods left add to one less than the rod that was sawn and only a rod of three or more can be sawn. When the row holds an odd number of gaps the blade runs true and eats nothing, so the two rods add to the whole rod and a rod of two saws into two ones. The setting holds for both players and no cut ever changes it.

Required artifacts include: `/app/fixtures`, `/app/docs/rules.md`, `/app/Sawmill.java`.

Author anonymous tagged this **hard** games task (sawmill, game, cli, rules, scoring).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `cb84d31f-de2f-4367-bbef-14b2bb8a827b_submission_2026-07-21T09_48_30.858Z.zip` is a task submission, not a Harbor job. 8 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
