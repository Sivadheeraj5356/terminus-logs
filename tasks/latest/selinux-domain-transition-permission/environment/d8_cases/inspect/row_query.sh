#!/bin/bash
set -euo pipefail

case_id="${1:-}"
entry_idx="${2:-}"

if [[ -z "$case_id" || -z "$entry_idx" ]]; then
  echo "usage: row_query.sh <case_id> <entry_idx>" >&2
  exit 2
fi

python3 - "$case_id" "$entry_idx" <<'PY'
import json
import sys
from pathlib import Path

case_id = sys.argv[1]
idx = int(sys.argv[2])
app = Path("/app")
obs = json.loads((app / "output" / "d8_observations.json").read_text())
rows = [r for r in obs["rows"] if r["case_id"] == case_id]
rows.sort(key=lambda r: int(r["entry_idx"]))
row = rows[idx]
print(json.dumps(row, sort_keys=True))
PY
