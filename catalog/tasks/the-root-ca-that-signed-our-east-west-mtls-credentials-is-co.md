# The root CA that signed our east-west mTLS credentials is confirmed compromised,

Submission: `9dc87873-29c5-4064-8182-29a6451f3d9d`  
Slug: `the-root-ca-that-signed-our-east-west-mtls-credentials-is-co`  
Latest archive: `9dc87873-29c5-4064-8182-29a6451f3d9d_submission_2026-07-19T10_44_00.303Z.zip`  
Revisions: 1

## Task summary

The root CA that signed our east-west mTLS credentials is confirmed compromised, so an attacker can impersonate every service that remains on the old credential generation. Produce the exact emergency rotation schedules for the three incident inventories described below. Leave `/app/task_file/scan_input/` unchanged. The three incident inventories are `/app/task_file/scan_input/credential_incident.txt`, `/app/task_file/scan_input/credential_incident_b.txt`, and `/app/task_file/scan_input/credential_incident_c.txt`. The format is whitespace-separated, ignores blank lines and lines beginning with `#`, and contains:

Required artifacts include: `/app/task_file/scan_input/`, `/app/task_file/scan_input/credential_incident.txt`, `/app/task_file/scan_input/credential_incident_b.txt`, `/app/task_file/scan_input/credential_incident_c.txt`, `/app/task_file/output/credential_schedule.json`, `/app/task_file/output/credential_schedule_b.json`, `/app/task_file/output/credential_schedule_c.json`.

Author Anonymous tagged this **hard** security task (mtls, credential-rotation, incident-response, certificate-authority-compromise, exact-scheduling).

Time estimates: expert ~480.0 min, junior ~1800.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `9dc87873-29c5-4064-8182-29a6451f3d9d_submission_2026-07-19T10_44_00.303Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
