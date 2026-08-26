#!/usr/bin/env bash
set -euo pipefail

log() { printf '[solve] %s\n' "$1"; }

cd "$(dirname "${BASH_SOURCE[0]}")"

log "apply source fixes"
patch -p0 -d /app < oracle.patch

cd /app
mkdir -p /app/output
rm -f /app/output/ops_row_report.json

log "run driver"
/app/bin/hx_ctl run

log "sanity-check output contract"
python3 <<'PY'
import json
from pathlib import Path

data = json.loads(Path("/app/output/ops_row_report.json").read_text(encoding="utf-8"))
assert data["summary"]["sync_label"] == "steady"
for row in data["rows"]:
    assert row["bind_rc"] == 1 and row["lock_rc"] == 1 and row["unit_rc"] == 1
    assert row["drift_code"] == 0
PY

log "done"
