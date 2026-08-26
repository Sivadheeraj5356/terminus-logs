#!/bin/bash
set -euo pipefail

ENV="/app/environment"
OUT="/app/output/sandbox_observations.json"
DATA="/app/data/wasm"
FIXTURE="${1:-$ENV/fixtures/waves/recovery-wave.json}"

mkdir -p /app/output "$DATA"

python3 - <<PY
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app/environment")
from driver.recovery_runner import run_recovery, write_observations

spec = json.loads(Path("$FIXTURE").read_text())
doc = run_recovery(spec, Path("$DATA"))
write_observations(doc, Path("$OUT"))
PY
