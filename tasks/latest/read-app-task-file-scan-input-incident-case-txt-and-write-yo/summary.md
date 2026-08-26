# Read `/app/task_file/scan_input/incident_case.txt` and write your answer to `/ap

- **UUID:** `ff0fa7b0-8f21-4254-b95d-b7e61a65a407`
- **Slug:** `read-app-task-file-scan-input-incident-case-txt-and-write-yo`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Read `/app/task_file/scan_input/incident_case.txt` and write your answer to `/app/task_file/output/containment_schedule.json`. Leave everything under `scan_input` unchanged.

This is a polar observatory calibration task: the case file describes a routed sensor graph, several independent interference hypotheses over that graph, transfer routes that can spread compromise, shielded instruments, maintenance paths, and telemetry evidence. Produce one wave-by-wave schedule that maximizes the response score.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
