#!/bin/bash
# Verifier-owned MLflow startup — do not use /app/scripts/start_mlflow.sh at scoring time.
set -euo pipefail

TRACKING_DIR="/app/mlflow_tracking"
ARTIFACT_ROOT="/app/mlflow_artifacts"
PID_FILE="/tmp/mlflow.pid"

mkdir -p "$TRACKING_DIR" "$ARTIFACT_ROOT"

if [ "${MLFLOW_FORCE_RESTART:-0}" = "1" ]; then
  pkill -9 -f "mlflow server" 2>/dev/null || true
  rm -f "$PID_FILE" /tmp/mlflow.log
  sleep 1
elif [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=1)" 2>/dev/null; then
    exit 0
  fi
  pkill -9 -f "mlflow server" 2>/dev/null || true
  rm -f "$PID_FILE" /tmp/mlflow.log
  sleep 1
fi

mlflow server \
  --host 127.0.0.1 \
  --port 5000 \
  --backend-store-uri "file://${TRACKING_DIR}" \
  --default-artifact-root "file://${ARTIFACT_ROOT}" \
  >/tmp/mlflow.log 2>&1 &

echo $! >"$PID_FILE"

for _ in $(seq 1 60); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=1)" 2>/dev/null; then
    exit 0
  fi
  sleep 0.5
done

echo "MLflow server failed to start" >&2
exit 1
