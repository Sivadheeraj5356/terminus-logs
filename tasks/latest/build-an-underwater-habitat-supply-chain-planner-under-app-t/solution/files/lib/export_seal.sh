#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
source "${APP_ROOT}/lib/common.sh"
python3 - <<'PY'
import hashlib,json
from pathlib import Path
APP=Path("/app")
man=json.loads((APP/"state/ingest-manifest.json").read_text())
bind=json.loads((APP/"state/export-bind.json").read_text())
report=json.loads((APP/"output/utilization-report.json").read_text())
body={"schema_version":1,"run_sequence":man["run_sequence"],"bind_hash":bind["bind_hash"],
      "rov_hash":bind["rov_hash"],"plan_fingerprint":report["fingerprint"]}
body["seal_hash"]=hashlib.sha256(json.dumps({k:body[k] for k in body if k!="seal_hash"},separators=(",",":"),sort_keys=True).encode()).hexdigest()
(APP/"state/export-seal.json").write_text(json.dumps(body,indent=2)+"\n")
PY
