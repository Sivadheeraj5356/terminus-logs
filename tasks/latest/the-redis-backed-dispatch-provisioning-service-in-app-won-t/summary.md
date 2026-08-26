# The Redis-backed dispatch provisioning service in /app won't come up. The servic

- **UUID:** `951c3201-2c2f-4073-bdbf-e5884f509fde`
- **Slug:** `the-redis-backed-dispatch-provisioning-service-in-app-won-t`
- **Category:** system-administration
- **Difficulty:** medium

## Summary

The Redis-backed dispatch provisioning service in /app won't come up. The service code is fine, but it's carrying stale configuration from an old docker-compose deployment: it can't reach Redis, and even once it does its file paths are wrong.

Redis itself is set up in /app/config/redis.conf and the service reads its own settings from /app/config (a service.json base with a service.overrides overlay). Get the service talking to the Redis instance described by redis.conf and bring it online, then run `node /app/scripts/reconcile-client.js` so it completes a run and writes /app/output/reconciliation-report.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
