#!/usr/bin/env bash
set -euo pipefail

PID_FILE="/tmp/chamberd.pid"
if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE" || true)"
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 0.1
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

pkill -f "socat TCP-LISTEN:.*handle_request" 2>/dev/null || true
pkill -x chamberd 2>/dev/null || true
pkill -f "strace .*launch_wrapper" 2>/dev/null || true

for _ in $(seq 1 20); do
  if [ -z "$(pgrep -x chamberd || true)" ]; then
    break
  fi
  sleep 0.05
done
true
