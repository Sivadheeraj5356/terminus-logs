# A wildlife photographer is planning the next tour and has forty subjects lined u

Submission: `55a3bdbe-2ac2-45c9-b10d-cb00799b5237`  
Slug: `a-wildlife-photographer-is-planning-the-next-tour-and-has-fo`  
Latest archive: `55a3bdbe-2ac2-45c9-b10d-cb00799b5237_submission_2026-07-18T16_04_12.220Z.zip`  
Revisions: 4

## Task summary

A wildlife photographer is planning the next tour and has forty subjects lined up to shoot, su-01 through su-40. Each one needs a frame budget going in: how many frames to spend from a shared public hide, and how many from a private guided sit. The hide is the cheap route. It bills at `hide_cost` per frame but works off a single ration, `hide_frame_budget` frames to be split among all forty subjects, so once that ration is gone the rest of a subject's frames come from the guided route at the steeper `guide_cost`. What the tour is really after is one keeper on every subject. Any single frame either keeps (the subject sharp, an eye lit, wingtips inside the frame) or it is a miss, at a rate that belongs to the subject; because frames fall independently, n of them bring home at least one keeper with probability 1-(1-p)^n. The aim is to carry every subject over the `keeper_floor` published in /app/environment/data/shoot_policy.json at the lowest committed cost the plan can reach. Committed cost is totted up across the list: each subject's hide frames at its `hide_cost`, plus its guided frames at its `guide_cost`. The `cost_ceiling` in that same policy file is firm. A plan that runs past it is refused outright, and so is one that lets any subject come in under the floor. What the ceiling leaves you is slack to go deep on a handful of subjects, not to raise the whole list a step. A subject whose rate you genuinely cannot fix is worth a heavy count, and the budget will wear that; try instead to edge all forty upward at once and the small overages pile up until the total clears...

Required artifacts include: `/app/environment/data/shoot_policy.json`, `/app/environment/data/frame_log.csv`, `/app/environment`, `/app/environment/data`, `/app/environment/data/README.md`.

Author anonymous tagged this **hard** scientific-computing task (rust, scientific-computing, estimation, uncertainty, reliability).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `55a3bdbe-2ac2-45c9-b10d-cb00799b5237_submission_2026-07-18T16_04_12.220Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
