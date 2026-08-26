# Our message broker's permissions export in /app/rabbitmq_definitions.json

Submission: `6e613bd6-685e-4b60-8c6f-971e419341e6`  
Slug: `our-message-broker-s-permissions-export-in-app-rabbitmq-defi`  
Latest archive: `6e613bd6-685e-4b60-8c6f-971e419341e6_submission_2026-07-17T02_10_32.926Z.zip`  
Revisions in Dropbox: 1

## Task summary

Our message broker's permissions export in /app/rabbitmq_definitions.json hasn't been reconciled since the last few access-review tickets, a recent incident's temporary access grant, and a security review. Bring the permissions array into compliance with /app/RABBITMQ_ACCESS_POLICY.md, cross-referencing /app/PERMISSION_CHANGELOG.md, /app/DOWNSTREAM_CONSUMERS.md, /app/PROTECTED_SERVICE_ACCOUNTS.md, and /app/INCIDENT_ACCESS.md to work out what the correct end state actually is right now. Existing entries may be missing outright, over-granted, under-granted, or stale; the correct end state is whatever the policy and its reference documents imply, not just a correction of what's already there. The policy document explains how a user's capability on a resource is decided, which of the reference files can override the plain tier-based defaults and how, how a temporary grant's validity window is evaluated, and caps on how many accounts may hold each of the two most destructive capabilities across the confidential vhosts combined.

Required artifacts include: `/app/rabbitmq_definitions.json`, `/app/RABBITMQ_ACCESS_POLICY.md`, `/app/PERMISSION_CHANGELOG.md`, `/app/DOWNSTREAM_CONSUMERS.md`, `/app/PROTECTED_SERVICE_ACCOUNTS.md`, `/app/INCIDENT_ACCESS.md`.

Author task-author tagged this **hard** security task (rabbitmq, message-broker, access-control, policy-remediation, time-boxed-access).

Time estimates: expert ~80 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `6e613bd6-685e-4b60-8c6f-971e419341e6_submission_2026-07-17T02_10_32.926Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
