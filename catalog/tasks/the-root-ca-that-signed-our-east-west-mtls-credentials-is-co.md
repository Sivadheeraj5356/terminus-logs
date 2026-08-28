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

Harbor trials: 1 — 1 solved, 0 valid fail, 0 timeout, 0 infra.

## Agent summary

Skipping image OS validation for hb__c26174bc4a871ed7b1883c8ada036827: docker inspect returned 1 Collecting main service artifacts

## Stump the models?

- oracle: 0/1 valid fail (0.0%)
- Timeouts excluded: 0; infra excluded: 0
- Band: `too_easy`
