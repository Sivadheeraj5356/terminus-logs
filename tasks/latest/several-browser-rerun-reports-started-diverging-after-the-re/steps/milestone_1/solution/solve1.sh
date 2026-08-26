#!/bin/bash
# solution/solve1.sh — Milestone 1 oracle
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/apply_m1_fixes.sh"

echo "[m1] Running report to validate fix..."
cd /app
node cli.js report

TOTAL=$(node -e "const r = require('./logs/report.json'); console.log(r.total_flaky_combos);")
echo "[m1] total_flaky_combos = $TOTAL"
if [ "$TOTAL" -ne 6 ]; then
  echo "[m1] ERROR: Expected 6 flaky combos, got $TOTAL"
  exit 1
fi

echo "[m1] Milestone 1 oracle complete. report.json validated."
