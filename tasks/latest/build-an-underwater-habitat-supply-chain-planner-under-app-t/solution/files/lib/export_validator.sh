#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
source "${APP_ROOT}/lib/common.sh"
python3 - <<'PY'
import json
from pathlib import Path
APP=Path("/app")
freeze=json.loads((APP/"state/o2-priority-freeze.json").read_text())
by={e["cargo_id"]:e["o2"] for e in freeze["entries"]}
plan=json.loads((APP/"output/resupply-plan.json").read_text())
for line in plan["lines"]:
    expected=by.get(line["cargo_id"])
    if expected is None or line["o2"]!=expected:
        raise SystemExit("o2 freeze mismatch")
PY
