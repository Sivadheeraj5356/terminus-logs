#!/bin/bash
set -euo pipefail

cd /app
python3 - <<'PY'
import json
from pathlib import Path

doc = json.loads(Path("/app/data/manifest.json").read_text(encoding="utf-8"))
for entry in doc["consumers"]:
    for key in ("graph", "ledger", "consumer"):
        path = Path(entry[key])
        if not path.exists():
            raise SystemExit(f"missing fixture: {path}")
PY

/app/launcher/lf_align
