#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/reset-demo-state.sh
./scripts/build.sh

BACKEND_SOCK="/tmp/demo-backend.sock"
PROXY_SOCK="/tmp/demo-proxy.sock"
READY="/tmp/demo-proxy.ready"
TRACE="/output/request-trace.json"
CHUNK_REQ="/tmp/demo-chunked.http"

python3 - <<'PY'
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("gf", "scripts/generate-fixtures.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
sem = {
    "request_id": "req-restart-chunk",
    "profile_id": "current-2026",
    "profile_epoch": 1,
    "tenant": "demo",
    "key_id": "demo-key-1",
    "key_epoch": 1,
    "method": "POST",
    "authority": "api.local",
    "wire_target": "/v1/restart",
    "canonical_target": "/v1/restart",
    "canonical_headers": [
        {"name": "host", "value": "api.local"},
        {"name": "content-type", "value": "application/json"},
    ],
    "entity_body_sha256": mod.body_digest(b'{"queued":true}'),
    "entity_body_length": 14,
    "request_nonce": "nonce-restart-1",
    "wire_headers": [{"name": "Content-Type", "value": "application/json"}],
    "chunked": True,
    "chunk_size": 5,
}
Path("/tmp/demo-chunked.http").write_bytes(mod.build_request(sem, 2, [], b'{"queued":true}'))
PY

rm -f "$BACKEND_SOCK" "$PROXY_SOCK" "$READY" "$TRACE"
find state/spool -mindepth 1 -delete 2>/dev/null || true

# start proxy without backend to force spool
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

socat - UNIX-CONNECT:"$PROXY_SOCK" < "$CHUNK_REQ" > /tmp/demo-restart-queue.txt || true
kill "$PROXY_PID" 2>/dev/null || true
wait "$PROXY_PID" 2>/dev/null || true

echo "--- spool records ---"
bin/spool-inspect --dir state/spool || true

bin/backend-capture --listen-unix "$BACKEND_SOCK" --output /tmp/demo-backend-capture.json &
BACKEND_PID=$!
sleep 0.3

bin/proxy-local recover \
  --backend-unix "$BACKEND_SOCK" \
  --config config/proxy.json \
  --trace "$TRACE" \
  --audit-log /logs/agent/proxy-audit.jsonl

kill "$BACKEND_PID" 2>/dev/null || true
wait "$BACKEND_PID" 2>/dev/null || true

echo "--- backend after recover ---"
cat /tmp/demo-backend-capture.json
echo "--- trace ---"
cat "$TRACE"
echo "demo-restart complete (expect replay wire re-parse drift on chunked body)"
