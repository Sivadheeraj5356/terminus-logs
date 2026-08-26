#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
source "${APP_ROOT}/lib/common.sh"
python3 - "$RUN_SEQUENCE_FILE" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
seq = 0
if path.is_file():
    seq = json.loads(path.read_text()).get("run_sequence", 0)
seq += 1
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({"run_sequence": seq}, indent=2))
print(seq)
PY
