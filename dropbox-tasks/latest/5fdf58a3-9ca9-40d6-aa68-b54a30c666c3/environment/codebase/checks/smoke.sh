#!/usr/bin/env bash
set -euo pipefail

node /app/src/worker.js >/tmp/worker-smoke.json
python3 - <<'PY'
import json
with open('/tmp/worker-smoke.json','r',encoding='utf-8') as fh:
    data = json.load(fh)
assert isinstance(data, dict)
assert 'status' in data
assert data.get('status') != 'not_implemented'
PY

echo "smoke ok"
