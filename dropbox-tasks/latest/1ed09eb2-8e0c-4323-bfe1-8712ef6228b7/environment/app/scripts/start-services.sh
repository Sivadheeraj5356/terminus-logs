#!/bin/bash
# Brings up the Redis instance holding the link ledger registry and the Slim
# interface API. Safe to call repeatedly: already-running services are left
# alone.
set -euo pipefail

mkdir -p /var/log/linkreg-api /var/lib/redis

if ! redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1; then
    redis-server /etc/redis/linkreg.conf
fi

for _ in $(seq 1 60); do
    if redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1; then
        break
    fi
    sleep 0.25
done

if ! curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
    nohup php -S 127.0.0.1:8080 -t /app/api/public /app/api/public/index.php \
        >>/var/log/linkreg-api/server.log 2>&1 &
    disown || true
fi

for _ in $(seq 1 60); do
    if curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
        break
    fi
    sleep 0.25
done

redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null
curl -sf http://127.0.0.1:8080/health >/dev/null
echo "redis 127.0.0.1:6379 and api 127.0.0.1:8080 are up"
