#!/bin/bash
set -euo pipefail

REDIS_PORT="${REDIS_PORT:-6379}"
export REDIS_URL="redis://127.0.0.1:${REDIS_PORT}"
export REDIS_FIXTURES_DIR="/app/redis_fixtures"

if ! redis-cli -p "${REDIS_PORT}" ping >/dev/null 2>&1; then
  redis-server --port "${REDIS_PORT}" --daemonize yes --save "" --appendonly no
  sleep 0.3
fi

node /app/scripts/seed_redis.mjs
