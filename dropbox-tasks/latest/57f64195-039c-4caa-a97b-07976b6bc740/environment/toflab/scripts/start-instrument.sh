#!/bin/bash
set -euo pipefail

PIDFILE=/tmp/toflab-instrument.pid
LOGFILE=/tmp/toflab-instrument.log

if [[ -f "$PIDFILE" ]]; then
  old_pid=$(cat "$PIDFILE" || true)
  if [[ -n "${old_pid}" ]] && kill -0 "$old_pid" 2>/dev/null; then
    kill "$old_pid" 2>/dev/null || true
    sleep 0.5
  fi
  rm -f "$PIDFILE"
fi

python3 /app/instrument/app.py >"$LOGFILE" 2>&1 &
echo $! >"$PIDFILE"

for _ in $(seq 1 50); do
  if python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8791/health", timeout=0.2)' 2>/dev/null; then
    exit 0
  fi
  sleep 0.1
done

echo "instrument telemetry failed to become ready" >&2
cat "$LOGFILE" >&2 || true
exit 1
