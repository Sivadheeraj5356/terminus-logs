#!/usr/bin/env bash
probe_host_only() {
  local tbl="$1"
  python3 - "$tbl" <<'PY'
import json, sys
from pathlib import Path
names = sorted(p.stem for p in Path("/app/environment/bundles/waves").glob("*.json"))
Path(sys.argv[1]).write_text(json.dumps({"order": names}) + "\n")
PY
}
