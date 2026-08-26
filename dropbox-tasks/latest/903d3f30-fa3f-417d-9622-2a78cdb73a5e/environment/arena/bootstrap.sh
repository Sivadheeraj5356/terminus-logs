#!/bin/sh
set -eu
umask 077

. /opt/arena-private/difficulty_knobs.conf

ARENA_SOCKET=${ARENA_SOCKET:-/run/arena/arena.sock}
export ARENA_SOCKET

actual_model_sha256=$(sha256sum "$OPPONENT_MODEL_FILE")
actual_model_sha256=${actual_model_sha256%% *}
if [ "$actual_model_sha256" != "$OPPONENT_MODEL_SHA256" ]; then
  echo "Tidevault checkpoint digest differs from frozen configuration" >&2
  exit 1
fi

rm -f -- "$ARENA_SOCKET"
/usr/bin/python3 -I /opt/arena-private/referee.py \
  --socket "$ARENA_SOCKET" \
  --model "$OPPONENT_MODEL_FILE" \
  --model-id "$OPPONENT_MODEL_ID" \
  --model-sha256 "$OPPONENT_MODEL_SHA256" \
  --dataset-sha256 "$OPPONENT_DATASET_SHA256" \
  --node-budget "$OPPONENT_NODE_BUDGET" \
  --width "$OPPONENT_SEARCH_WIDTH" \
  --max-depth "$OPPONENT_MAX_DEPTH" \
  --seed "$OPPONENT_SEED" \
  --selection-profile "$OPPONENT_SELECTION_PROFILE" \
  --root-temperature-milli "$OPPONENT_ROOT_TEMPERATURE_MILLI" \
  --root-rank-lapse-permille "$OPPONENT_ROOT_RANK_LAPSE_PERMILLE" \
  --move-time-limit-ms "$OPPONENT_MOVE_TIME_LIMIT_MS" \
  >>/opt/arena-private/referee.log 2>&1 &
referee_pid=$!

attempt=0
while ! /opt/arena-private/healthcheck.sh >/dev/null 2>&1; do
  if ! kill -0 "$referee_pid" 2>/dev/null; then
    echo "Tidevault referee failed during startup" >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 200 ]; then
    echo "Tidevault referee did not become ready" >&2
    exit 1
  fi
  sleep 0.1
done

if [ "$#" -eq 0 ]; then
  wait "$referee_pid"
  exit $?
fi

exec "$@"
