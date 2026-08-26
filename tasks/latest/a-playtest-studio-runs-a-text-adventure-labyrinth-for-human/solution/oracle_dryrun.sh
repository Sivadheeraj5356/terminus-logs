#!/usr/bin/env bash
# Smoke the rebuilt binary: health, session create, probe, assemble, and a
# combined oracle call against the bundled labyrinth world.
set -euo pipefail

ADDR="127.0.0.1:18765"
/app/bin/labyrinth-oracle serve --addr "${ADDR}" &
PID=$!
cleanup() {
  kill "${PID}" >/dev/null 2>&1 || true
  wait "${PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

python3 - <<'PY'
import json
import time
import urllib.error
import urllib.request

base = "http://127.0.0.1:18765"

def get(path):
    with urllib.request.urlopen(base + path, timeout=2) as resp:
        return resp.status, json.load(resp)

def post(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        return resp.status, json.load(resp)

for _ in range(40):
    try:
        status, body = get("/health")
        if status == 200 and body.get("status") == "ok":
            break
    except Exception:
        time.sleep(0.25)
else:
    raise SystemExit("oracle never became healthy")

status, session = post("/sessions", {"world_id": "labyrinth", "room_id": "atrium"})
assert status == 200 or status == 201
sid = session["session_id"]
assert sid

status, probe = post(f"/sessions/{sid}/probe")
assert status == 200
assert "gather_seq" in probe

status, assembled = post(f"/sessions/{sid}/assemble")
assert status == 200
assert "hints" in assembled

status, oracle = get(f"/sessions/{sid}/oracle")
assert status == 200
assert "hints" in oracle
print(f"oracle-smoke-ok {sid}")
PY
