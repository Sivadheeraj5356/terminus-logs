# The Granite beamline group needs its short-exposure calibration packet settled b

Submission: `4b2e2aeb-b0c0-467e-adc9-f185b5a9a4ab`  
Slug: `the-granite-beamline-group-needs-its-short-exposure-calibrat`  
Latest archive: `4b2e2aeb-b0c0-467e-adc9-f185b5a9a4ab_submission_2026-07-18T12_07_20.276Z.zip`  
Revisions: 2

## Task summary

The Granite beamline group needs its short-exposure calibration packet settled before the next horn run. The operations team needs a schedule that delivers the requested neutrino flux without exceeding horn temperature, transition-current, or shielding limits. Build the local calculator in `/app/main.js`; `/app/task_file/beamline-tuner` is the command the control-room staff will use. The public laboratory protocol and score-sheet contract are at `/app/task_file/beamline_operations_protocol.txt`. With no arguments, the command uses `/app/task_file/beamline_case.json` and writes the official results to `/app/task_file/output`. With exactly two arguments, the first is an alternate case file and the second is its result directory; create that directory when it does not exist. In either mode, replace the three official result files only: `profile_screen.json`, `thermal_trace.json`, and `beam_plan.json`. Preserve the case file supplied for the run.

Required artifacts include: `/app/main.js`, `/app/task_file/beamline-tuner`, `/app/task_file/beamline_operations_protocol.txt`, `/app/task_file/beamline_case.json`, `/app/task_file/output`.

Author Anonymous tagged this **hard** scientific-computing task (neutrino-physics, accelerator-physics, magnetic-horns, beam-transport, thermal-simulation).

Time estimates: expert ~180.0 min, junior ~900.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `4b2e2aeb-b0c0-467e-adc9-f185b5a9a4ab_submission_2026-07-18T12_07_20.276Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
