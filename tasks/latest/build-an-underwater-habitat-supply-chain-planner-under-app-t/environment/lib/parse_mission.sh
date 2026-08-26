#!/usr/bin/env bash
set -euo pipefail
root="$1"
python3 - "$root" <<'PY'
import json, sys
from pathlib import Path
r=Path(sys.argv[1])
rows=[json.loads(l) for l in (r/"cargo.jsonl").read_text().splitlines() if l.strip()]
rows.sort(key=lambda e:e["cargo_id"])
hab=json.loads((r/"habitat.json").read_text())
print(json.dumps({"cargo":rows,"habitat":hab}))
PY
