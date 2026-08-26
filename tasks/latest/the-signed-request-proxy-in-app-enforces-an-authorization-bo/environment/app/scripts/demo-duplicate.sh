#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/reset-demo-state.sh
./scripts/build.sh

BACKEND_SOCK="/tmp/demo-backend.sock"
PROXY_SOCK="/tmp/demo-proxy.sock"
READY="/tmp/demo-proxy.ready"
CAPTURE="/tmp/demo-backend-capture.json"
TRACE="/output/request-trace.json"

rm -f "$BACKEND_SOCK" "$PROXY_SOCK" "$READY" "$CAPTURE" "$TRACE"

bin/backend-capture --listen-unix "$BACKEND_SOCK" --output "$CAPTURE" &
BACKEND_PID=$!
sleep 0.3

bin/proxy-local serve \
  --listen-unix "$PROXY_SOCK" \
  --backend-unix "$BACKEND_SOCK" \
  --config config/proxy.json \
  --trace "$TRACE" \
  --audit-log /logs/agent/proxy-audit.jsonl \
  --ready-file "$READY" &
PROXY_PID=$!

for _ in $(seq 1 50); do
  [[ -f "$READY" ]] && break
  sleep 0.1
done

socat - UNIX-CONNECT:"$PROXY_SOCK" < data/requests/duplicate-list-current.http > /tmp/demo-duplicate-response.txt || true

kill "$PROXY_PID" "$BACKEND_PID" 2>/dev/null || true
wait "$PROXY_PID" 2>/dev/null || true
wait "$BACKEND_PID" 2>/dev/null || true

echo "--- response ---"
cat /tmp/demo-duplicate-response.txt
echo "--- backend capture ---"
cat "$CAPTURE"
echo "--- trace canonical headers ---"
python3 - <<'PY'
import json
doc=json.load(open("/output/request-trace.json"))
for e in doc.get("entries",[]):
    print("decision", e.get("decision"), "reason", e.get("reason"))
    print("canonical", e.get("canonical_headers"))
PY
echo "demo-duplicate complete (expect verify/forward header universe mismatch)"
