#!/bin/bash
set -euo pipefail

# Oracle solution. The dispatch service code is complete; the task is to bring
# the service into working order by provisioning the Redis data directory and
# reconciling the stale service configuration with how Redis is actually
# provisioned in /app/config/redis.conf (nonstandard port 6390, requirepass
# devsecret).

# 1) Provision the Redis data directory referenced by redis.conf `dir`.
mkdir -p /app/run

# 2) service.overrides wins over service.json for the Redis URL, so the
#    authenticated connection string must be corrected in the winning layer.
cat > /app/config/service.overrides <<'EOF'
# Per-host overrides for the dispatch service. Any key set here wins over the
# matching value in service.json (see src/config.js).
DISPATCH_REDIS_URL=redis://:devsecret@127.0.0.1:6390
EOF

# 3) Correct the stale paths (and the base URL) in service.json.
cat > /app/config/service.json <<'EOF'
{
  "redis": { "url": "redis://:devsecret@127.0.0.1:6390" },
  "http": { "port": 3000 },
  "canonicalCsv": "/app/data/taxi_zone_lookup.csv",
  "overridesArchive": "/app/dispatch-config.tar.gz",
  "reportPath": "/app/output/reconciliation-report.json"
}
EOF

# 4) Bring the stack up and run the reconciliation so the report is produced.
redis-server /app/config/redis.conf
for _ in $(seq 1 50); do
    redis-cli -p 6390 -a devsecret ping >/dev/null 2>&1 && break
    sleep 0.2
done
node /app/src/server.js >/tmp/dispatch-server.log 2>&1 &
for _ in $(seq 1 75); do
    if (exec 3<>/dev/tcp/127.0.0.1/3000) 2>/dev/null; then exec 3>&- 3<&-; break; fi
    sleep 0.2
done
node /app/scripts/seed.js
node /app/scripts/reconcile-client.js

echo "dispatch service configured and reconciled"
