# # Milestone 2

Submission: `03f13af6-a87b-4911-92d0-9cf000d5aca9`  
Slug: `milestone-2`  
Latest archive: `03f13af6-a87b-4911-92d0-9cf000d5aca9_submission_2026-07-12T13_41_45.826Z.zip`  
Revisions in Dropbox: 1

## Task summary

Implement this milestone in /app/main.c. This milestone builds on the last milestone by locating the Morse Code Key and operator in a moving vehicle. During the test, the operator of the Morse Code key will be traveling in a car moving at a speed from 0 to 20 meters/second around turns and up and down hills with a minimum radius of 30 meters. The car has a maximum acceleration from 0-20 meters/second of 5 seconds. The car can brake without skidding at 0.9g on the surface of the road given the conditions. The road may be banked up to 15 degrees during turns. Because the road can be banked, the downward motion of the key's strike axis will be tilted and split between the y and z axes. Left and right turns will be in the y axis and acceleration and braking will be in the x axis.

Required artifacts include: `/app/main.c`.

Author anonymous tagged this **medium** scientific-computing task (games, physics, Morse Code, puzzles).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `03f13af6-a87b-4911-92d0-9cf000d5aca9_submission_2026-07-12T13_41_45.826Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
