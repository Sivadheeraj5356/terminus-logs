#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /app/state/plan-seal.json ]]; then
  echo "missing plan seal" >&2
  exit 2
fi

python3 <<'PY'
import json, sys
plan = json.load(open("/app/output/rollback-plan.json"))
seal = json.load(open("/app/state/plan-seal.json"))
if seal.get("plan_hash") != plan.get("hash"):
    print("plan seal hash mismatch", file=sys.stderr)
    sys.exit(4)
PY

if [[ ! -f /app/state/rollback-witness-bundle.json ]]; then
  echo "missing witness bundle" >&2
  exit 17
fi

python3 <<'PY'
import hashlib, json, sys
manifest = json.load(open("/app/state/inspect-manifest.json"))
status = json.load(open("/app/state/deploy-status.json"))
lines = sorted(f"{svc}|{row['status']}" for svc, row in status["services"].items())
digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
if manifest.get("release_digest") != digest:
    print("inspect manifest release_digest stale", file=sys.stderr)
    sys.exit(6)
PY

python3 <<'PY'
import json, sys
plan = json.load(open("/app/output/rollback-plan.json"))
graph = json.load(open("/app/data/topology/rollback-graph.json"))
order = plan["steps"]
pos = {s: i for i, s in enumerate(order)}
for svc in order:
    for dep in graph.get(svc, []):
        if dep in pos and pos[dep] < pos[svc]:
            print(f"rollback order invalid: {dep} before {svc}", file=sys.stderr)
            sys.exit(3)
PY

mkdir -p /app/state
echo "ok" > /app/state/rollback-complete.ok
