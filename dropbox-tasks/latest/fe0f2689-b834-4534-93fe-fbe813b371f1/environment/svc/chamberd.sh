#!/usr/bin/env bash
set -euo pipefail

ROOT="/app/environment"
CFG="$ROOT/config/service.toml"
GRAPH_KEY="$(awk -F'=' '/^graph_key/ {gsub(/[ "\t]/,"",$2); print $2}' "$CFG")"
ENDPOINT="$(awk -F'=' '/^endpoint/ {gsub(/[ "\t]/,"",$2); print $2}' "$CFG")"
PID_FILE="$(awk -F'=' '/^pid_file/ {gsub(/[ "\t]/,"",$2); print $2}' "$CFG")"
TRACE_LOG="$(awk -F'=' '/^trace_log/ {gsub(/[ "\t]/,"",$2); print $2}' "$CFG")"
PROC_NAME="$(awk -F'=' '/^proc_name/ {gsub(/[ "\t]/,"",$2); print $2}' "$CFG")"

GRAPH_PATH="$ROOT/vault/graphs/${GRAPH_KEY}.json"
if [ ! -f "$GRAPH_PATH" ]; then
  echo "missing graph: $GRAPH_PATH" >&2
  exit 1
fi

PORT="$("$ROOT/svc/select_bind.sh")"
export CHAMBER_GRAPH_PATH="$GRAPH_PATH"
export CHAMBER_ENDPOINT="$ENDPOINT"
export CHAMBER_PORT="$PORT"
export CHAMBER_HANDLER="$ROOT/svc/handle_request.sh"
export CHAMBER_PROC_NAME="$PROC_NAME"

rm -f "$TRACE_LOG" "$PID_FILE"

strace -f -o "$TRACE_LOG" -e trace=open,openat \
  bash "$ROOT/svc/launch_wrapper.sh" \
  >/tmp/chamberd.stdout 2>/tmp/chamberd.stderr &
STRACE_PID=$!

for _ in $(seq 1 50); do
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq ":${PORT}$"; then
    # Prefer the renamed listener; fall back to the strace parent.
    LISTEN_PID="$(pgrep -nx "$PROC_NAME" || true)"
    if [ -z "$LISTEN_PID" ]; then
      LISTEN_PID="$STRACE_PID"
    fi
    echo "$LISTEN_PID" >"$PID_FILE"
    exit 0
  fi
  sleep 0.1
done

echo "listener failed to bind on ${PORT}" >&2
exit 1
