#!/bin/bash
set -euo pipefail

ROOT="/app/environment"
SIM="${ROOT}/bin/h7_sim"

if [[ $# -lt 2 ]]; then
  echo "usage: probe_play.sh <training-or-puzzle.json> <step,step,...>" >&2
  exit 2
fi

BOARD="$1"
STEPS_CSV="$2"
TMP="$(mktemp /tmp/h7-probe-XXXXXX.json)"

python3 - <<PY
import json
from pathlib import Path

board = json.loads(Path("${BOARD}").read_text())
steps = [int(x) for x in "${STEPS_CSV}".split(",") if x != ""]
board["steps"] = steps
Path("${TMP}").write_text(json.dumps(board))
PY

"${SIM}" "${TMP}"
rm -f "${TMP}"
