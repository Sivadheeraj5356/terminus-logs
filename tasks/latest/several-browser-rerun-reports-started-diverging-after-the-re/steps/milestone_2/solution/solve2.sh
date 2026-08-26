#!/bin/bash
# solution/solve2.sh — Milestone 2 oracle
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/apply_m2_fixes.sh"

python3 - <<'PY'
import sys
sys.path.insert(0, "/opt/verifier-reference")
from reference_flaky import prepare_valid_history_rows
prepare_valid_history_rows()
PY

echo "[m2] Running plan generation to validate..."
cd /app
node cli.js plan --session plan-sess-alpha

CHROMIUM_RETRIES=$(node -e "
  const p = require('./logs/plan.json');
  const c = p.projects.find(x => x.browser === 'chromium');
  console.log(c ? c.retries : 'NOT_FOUND');
")

echo "[m2] chromium retries = $CHROMIUM_RETRIES"
if [ "$CHROMIUM_RETRIES" != "3" ]; then
  echo "[m2] ERROR: Expected chromium retries=3, got $CHROMIUM_RETRIES"
  exit 1
fi

CHROMIUM_NAME=$(node -e "
  const p = require('./logs/plan.json');
  const c = p.projects.find(x => x.browser === 'chromium');
  console.log(c ? c.name : 'NOT_FOUND');
")
echo "[m2] chromium project name = $CHROMIUM_NAME"
if [ "$CHROMIUM_NAME" != "Desktop Chrome" ]; then
  echo "[m2] ERROR: Expected 'Desktop Chrome', got '$CHROMIUM_NAME'"
  exit 1
fi

TOTAL_SPECS=$(node -e "console.log(require('./logs/plan.json').total_specs)")
if [ "$TOTAL_SPECS" != "6" ]; then
  echo "[m2] ERROR: Expected total_specs=6, got $TOTAL_SPECS"
  exit 1
fi

echo "[m2] Milestone 2 oracle complete. plan.json validated."
