# Read `/app/task_file/scan_input/incident_case.txt` and write your answer to `/ap

Submission: `ff0fa7b0-8f21-4254-b95d-b7e61a65a407`  
Slug: `read-app-task-file-scan-input-incident-case-txt-and-write-yo`  
Latest archive: `ff0fa7b0-8f21-4254-b95d-b7e61a65a407_submission_2026-07-05T16_36_30.540Z.zip`  
Revisions: 1

## Task summary

Read `/app/task_file/scan_input/incident_case.txt` and write your answer to `/app/task_file/output/containment_schedule.json`. Leave everything under `scan_input` unchanged. This is a polar observatory calibration task: the case file describes a routed sensor graph, several independent interference hypotheses over that graph, transfer routes that can spread compromise, shielded instruments, maintenance paths, and telemetry evidence. Produce one wave-by-wave schedule that maximizes the response score. The complete row layout, action rules, simulation rules, scoring, tie-breaking, and JSON output contract are in `/app/task_file/guide.md`. Follow that specification exactly and keep the output exact, including ordering and field types.

Required artifacts include: `/app/task_file/scan_input/incident_case.txt`, `/app/task_file/output/containment_schedule.json`, `/app/task_file/guide.md`.

Author Anonymous tagged this **hard** scientific-computing task (combinatorial-optimization, state-space-search, graph-search, constraint-satisfaction, deterministic-serialization).

Time estimates: expert ~240.0 min, junior ~1080.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `ff0fa7b0-8f21-4254-b95d-b7e61a65a407_submission_2026-07-05T16_36_30.540Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
