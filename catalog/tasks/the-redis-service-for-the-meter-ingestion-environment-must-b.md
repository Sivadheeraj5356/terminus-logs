# The Redis service for the meter ingestion environment must be brought into compl

Submission: `2f5e899b-db87-448d-adf0-e88fc0d53a5b`  
Slug: `the-redis-service-for-the-meter-ingestion-environment-must-b`  
Latest archive: `2f5e899b-db87-448d-adf0-e88fc0d53a5b_submission_2026-07-16T13_24_31.132Z.zip`  
Revisions: 2

## Task summary

The Redis service for the meter ingestion environment must be brought into compliance with the operations standard in /app/docs/redis-operations-standard.md, then populated from /app/input/redis-hardened-meter-fixtures.tar.gz using the supplied migration utility at /app/bin/import-fixtures.php. Work only with the local files and services in the container. Apply the required changes to the existing Redis service and configuration described by the environment. The final Redis instance must be reachable on the interface and port approved by the standard, reject unauthenticated clients, expose only the approved ACL principals, disable the prohibited administrative commands, and use the required persistence locations and permissions. Ensure the persisted ACL configuration does not retain unnecessary default ACL directives (for example, directives that are not required by the operations standard). Do not modify the fixture archive, the operations standard, or the migration utility. After the migration is complete, publish /app/output/migration-receipt.json and /app/output/migration-receipt.sha256. The JSON must contain exactly schema_version, redis_endpoint, dataset, keyspace, security, and persistence; use the field names and values defined by the operations standard. Where a field represents multiple values, preserve it as a JSON array even if it contains only a single entry. Derive the data counts and canonical keyspace checksum from the running Redis instance. Serialize the JSON as UTF-8 with sorted keys, two space indentation, and a trailing newline. The digest file must...

Required artifacts include: `/app/docs/redis-operations-standard.md`, `/app/input/redis-hardened-meter-fixtures.tar.gz`, `/app/bin/import-fixtures.php`, `/app/output/migration-receipt.json`, `/app/output/migration-receipt.sha256`.

Author anonymous tagged this **hard** system-administration task (redis, acl, persistence, php-cli, security-hardening).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `2f5e899b-db87-448d-adf0-e88fc0d53a5b_submission_2026-07-16T13_24_31.132Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
