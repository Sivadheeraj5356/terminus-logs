#!/usr/bin/env bash
rev_touch() {
  local manifest_path="$1"
  python3 - "$manifest_path" <<'PY'
import json, sys
from pathlib import Path
manifest_path = Path(sys.argv[1])
ledger_path = Path("/app/.staging/epoch_ledger.json")
if not ledger_path.is_file():
    ledger_path.write_text(json.dumps({"rev": 0, "last_stamp": ""}) + "\n")
ledger = json.loads(ledger_path.read_text())
manifest = json.loads(manifest_path.read_text())
stamp = manifest.get("stamp", "")
ledger["rev"] = int(ledger.get("rev", 0)) + 1
ledger["last_stamp"] = stamp
ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
PY
}
