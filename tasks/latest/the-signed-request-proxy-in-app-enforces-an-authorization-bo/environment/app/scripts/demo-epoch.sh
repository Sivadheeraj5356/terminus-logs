#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/reset-demo-state.sh
./scripts/build.sh

BACKEND_SOCK="/tmp/demo-backend.sock"
PROXY_SOCK="/tmp/demo-proxy.sock"
READY="/tmp/demo-proxy.ready"
TRACE="/output/request-trace.json"

rm -f "$BACKEND_SOCK" "$PROXY_SOCK" "$READY" "$TRACE"

bin/backend-capture --listen-unix "$BACKEND_SOCK" --output /tmp/demo-backend-capture.json &
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

socat - UNIX-CONNECT:"$PROXY_SOCK" < data/requests/simple-current.http > /tmp/demo-epoch-a.txt || true
# second request uses alternate profile epoch via encoded target under same key identity
socat - UNIX-CONNECT:"$PROXY_SOCK" < data/requests/encoded-target-current.http > /tmp/demo-epoch-b.txt || true
socat - UNIX-CONNECT:"$PROXY_SOCK" < data/requests/simple-current.http > /tmp/demo-epoch-c.txt || true

kill "$PROXY_PID" "$BACKEND_PID" 2>/dev/null || true
wait "$PROXY_PID" 2>/dev/null || true
wait "$BACKEND_PID" 2>/dev/null || true

python3 - <<'PY'
import json
doc=json.load(open("/output/request-trace.json"))
for i,e in enumerate(doc.get("entries",[])):
    print(i, "cache_hit", e.get("cache_hit"), "target", e.get("canonical_target"))
PY
echo "demo-epoch complete (expect incomplete cache scope on repeated authority)"
