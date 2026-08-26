#!/usr/bin/env bash
set -euo pipefail
pkill -f '/app/bin/reelseal-policyapi' 2>/dev/null || true
sleep 0.2
nohup /app/bin/reelseal-policyapi >/tmp/reelseal-api.log 2>&1 &
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8742/health >/dev/null 2>&1; then
    exit 0
  fi
  sleep 0.15
done
echo "policy api failed to start" >&2
tail -n 50 /tmp/reelseal-api.log >&2 || true
exit 1
