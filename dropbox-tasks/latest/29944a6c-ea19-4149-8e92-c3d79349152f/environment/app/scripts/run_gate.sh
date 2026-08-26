#!/bin/bash
# Start the gate service in the background and record its pid so the
# verifier (and the oracle) can stop it cleanly with the paired
# `stop_gate.sh` invocation embedded below.
set -euo pipefail

APP=/app
BIN="$APP/bin"
JARS=/opt/jars
PIDFILE="$APP/gate.pid"
LOGFILE="$APP/gate.log"
CLASSPATH="$BIN/gate.jar:$JARS/h2.jar:$JARS/snakeyaml.jar"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "[run_gate] already running: pid=$(cat "$PIDFILE")"
    exit 0
fi

nohup java -Dfile.encoding=UTF-8 -cp "$CLASSPATH" gate.Main \
      >"$LOGFILE" 2>&1 &

echo $! > "$PIDFILE"
echo "[run_gate] started; pid=$(cat "$PIDFILE") log=$LOGFILE"

# Health-poll: return only when /health responds or 30s elapse.
for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:8971/health >/dev/null 2>&1; then
        echo "[run_gate] healthy after ${i}00ms"
        exit 0
    fi
    sleep 0.5
done

echo "[run_gate] never became healthy — last log:"
tail -50 "$LOGFILE" >&2 || true
exit 1
