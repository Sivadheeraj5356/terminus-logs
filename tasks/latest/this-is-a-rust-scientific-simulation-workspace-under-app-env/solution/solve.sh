#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
patch -d /app -p0 --batch < patches/all-fixes.patch
bash /app/environment/scripts/forge_all.sh
rm -f /app/output/session_ledger.json
bash /app/environment/scripts/run_k7.sh --suite g2 --ticks 12:0 --emit /app/output/session_ledger.json
python3 - <<'PY'
import json
from pathlib import Path

doc = json.loads(Path("/app/output/session_ledger.json").read_text())
assert doc["schema_version"] == 3, doc
assert doc["ticks"] == 120, doc
ids = sorted(r["scenario_id"] for r in doc["runs"])
assert ids == ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"], ids
assert "plane_trace_digest" in doc and "cadence_digest" in doc
assert "pool_trace_digest" in doc and "scenario_digest" in doc
assert doc["ledger_digest"]
assert all(r.get("recovery_epoch", -1) == 0 for r in doc["runs"])
print("oracle_status=converged")
PY
