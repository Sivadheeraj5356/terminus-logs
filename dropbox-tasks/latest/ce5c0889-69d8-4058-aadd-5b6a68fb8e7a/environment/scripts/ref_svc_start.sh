#!/bin/bash
set -euo pipefail
set -a
# shellcheck disable=SC1091
source /app/config/ports.conf
set +a

if [ -f /app/run/ref_svc.pid ]; then
  kill "$(cat /app/run/ref_svc.pid)" 2>/dev/null || true
  rm -f /app/run/ref_svc.pid
fi
mkdir -p /app/run
nohup node /app/svc/listen.js > /app/run/ref_svc.log 2>&1 &
echo $! > /app/run/ref_svc.pid

ready=0
for _ in $(seq 1 50); do
  if REF_HOST="$REF_HOST" REF_PORT="$REF_PORT" php -r '
    $host = getenv("REF_HOST") ?: "127.0.0.1";
    $port = getenv("REF_PORT") ?: "7088";
    $url = "http://{$host}:{$port}/v1/disputes?round_ids=102";
    $ctx = stream_context_create(["http" => ["timeout" => 1]]);
    exit(@file_get_contents($url, false, $ctx) === false ? 1 : 0);
  ' 2>/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$(cat /app/run/ref_svc.pid)" 2>/dev/null; then
    echo "referee service exited during startup" >&2
    cat /app/run/ref_svc.log >&2 || true
    exit 1
  fi
  sleep 0.2
done

if [ "$ready" -ne 1 ]; then
  echo "referee service failed to accept connections" >&2
  cat /app/run/ref_svc.log >&2 || true
  exit 1
fi

echo "referee service started"
