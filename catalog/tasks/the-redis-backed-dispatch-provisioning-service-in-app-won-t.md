# The Redis-backed dispatch provisioning service in /app won't come up. The servic

Submission: `951c3201-2c2f-4073-bdbf-e5884f509fde`  
Slug: `the-redis-backed-dispatch-provisioning-service-in-app-won-t`  
Latest archive: `951c3201-2c2f-4073-bdbf-e5884f509fde_submission_2026-07-20T08_16_13.165Z.zip`  
Revisions: 5

## Task summary

The Redis-backed dispatch provisioning service in /app won't come up. The service code is fine, but it's carrying stale configuration from an old docker-compose deployment: it can't reach Redis, and even once it does its file paths are wrong. Redis itself is set up in /app/config/redis.conf and the service reads its own settings from /app/config (a service.json base with a service.overrides overlay). Get the service talking to the Redis instance described by redis.conf and bring it online, then run `node /app/scripts/reconcile-client.js` so it completes a run and writes /app/output/reconciliation-report.json. Note that the Redis data directory referenced by redis.conf still needs to exist before Redis will start. Once the service is up, the reconcile run brings the drifted zone keyspace back in line with the canonical TLC lookup in /app/data/taxi_zone_lookup.csv, which takes precedence over the values currently in Redis. Operator overrides ship in the bundle the service unpacks, keyed by LocationID: a locked override is authoritative and wins over the canonical value, an unlocked override is only advisory and must be ignored, and any zone whose LocationID is not in the lookup is left untouched. Each zone carries a version that should increase by one only when one of its fields actually changes.

Required artifacts include: `/app/config/redis.conf`, `/app/config`, `/app/scripts/reconcile-client.js`, `/app/output/reconciliation-report.json`, `/app/data/taxi_zone_lookup.csv`.

Author anonymous tagged this **medium** system-administration task (redis, service-configuration, provisioning, reconciliation, idempotency).

Time estimates: expert ~60 min, junior ~150 min.

Harbor timeouts: agent 1200.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `951c3201-2c2f-4073-bdbf-e5884f509fde_submission_2026-07-20T08_16_13.165Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
