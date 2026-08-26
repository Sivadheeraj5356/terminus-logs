# I need you to recover a hidden sheaf binding over three rounds. A keeper hides o

Submission: `bc8074c0-90e9-4688-9a8b-4effa474f0e5`  
Slug: `i-need-you-to-recover-a-hidden-sheaf-binding-over-three-roun`  
Latest archive: `bc8074c0-90e9-4688-9a8b-4effa474f0e5_submission_2026-07-20T12_53_11.654Z.zip`  
Revisions: 1

## Task summary

I need you to recover a hidden sheaf binding over three rounds. A keeper hides one per round you never see: two stretches over twelve sheaves numbered 1 to 12. A stretch is an inclusive range of sheaves. The two stretches never touch, so at least one loose sheaf sits between them. Talk to the keeper only through /app/tally, which I built. Run tally help for the commands, tally read for where you stand. Name a handful with tally name 1,4,7, any set of distinct sheaves that leaves at least one out. You get one count: bound, how many of your handful's sheaves are bound. /app/sample-round.txt works it through. Exactly one reply per round is garbled: its bound count is off by exactly one. Every other reply is exact. The keeper fixes which reply it will garble when the round is set up, before you name anything; that position is the same no matter what handfuls you name, and the keeper never changes it in response to your play. You are not told which reply is the garbled one.

Required artifacts include: `/app/tally`, `/app/sample-round.txt`.

Author anonymous tagged this **hard** games task (deduction, gameplay, reasoning, interactive, interval-search).

Time estimates: expert ~40 min, junior ~110 min.

Harbor timeouts: agent 1800.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `bc8074c0-90e9-4688-9a8b-4effa474f0e5_submission_2026-07-20T12_53_11.654Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
