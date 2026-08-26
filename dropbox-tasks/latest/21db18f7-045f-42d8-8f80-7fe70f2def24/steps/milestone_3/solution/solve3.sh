#!/bin/bash
# solution/solve3.sh — Milestone 3 oracle (surgical patches only)
# Fixes three bugs in lib/executor.js:
# 1. executeplan(): does not delete stale session results before inserting new ones
# 2. aggregateResults(): interrupted=1 rows not filtered out
# 3. aggregateResults(): failure records missing 'browser' field
# 4. executeplan(): consult filtered test_runs history per spec+browser
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/apply_m3_fixes.sh"

python3 - <<'PY'
import sys
sys.path.insert(0, "/opt/verifier-reference")
from reference_flaky import prepare_valid_history_rows, write_reference_plan
prepare_valid_history_rows()
write_reference_plan()
PY

echo "[m3] Running execution to validate..."
cd /app
node cli.js run --session plan-sess-alpha

# Validate browser field in failures
BROWSER_PRESENT=$(node -e "
  const r = require('./logs/execution_report.json');
  const ok = r.failures.every(f => typeof f.browser === 'string' && f.browser.length > 0);
  console.log(ok ? 'yes' : 'no');
")
echo "[m3] browser field in failures: $BROWSER_PRESENT"
[ "$BROWSER_PRESENT" = "yes" ] || { echo "[m3] ERROR: browser field missing in failures"; exit 1; }

# Validate idempotency — run again and check counts match
node cli.js run --session plan-sess-alpha
PASSED_1=$(node -e "console.log(require('./logs/execution_report.json').passed_count)")
node cli.js run --session plan-sess-alpha
PASSED_2=$(node -e "console.log(require('./logs/execution_report.json').passed_count)")
echo "[m3] Idempotency check: run1 passed=$PASSED_1, run2 passed=$PASSED_2"
[ "$PASSED_1" = "$PASSED_2" ] || { echo "[m3] ERROR: passed_count not idempotent ($PASSED_1 vs $PASSED_2)"; exit 1; }

# Validate only checkout and login fail on chromium
FAILED_SPECS=$(node -e "
  const r = require('./logs/execution_report.json');
  const specs = new Set(r.failures.map(f => f.spec_file));
  console.log(Array.from(specs).sort().join(','));
")
echo "[m3] Failed specs: $FAILED_SPECS"
[ "$FAILED_SPECS" = "tests/e2e/checkout.spec.ts,tests/e2e/login.spec.ts" ] || {
  echo "[m3] ERROR: Expected only checkout,login to fail; got $FAILED_SPECS";
  exit 1;
}

# Validate all failures are chromium only
CHROMIUM_ONLY=$(node -e "
  const r = require('./logs/execution_report.json');
  const ok = r.failures.every(f => f.browser === 'chromium');
  console.log(ok ? 'yes' : 'no');
")
echo "[m3] All failures on chromium: $CHROMIUM_ONLY"
[ "$CHROMIUM_ONLY" = "yes" ] || { echo "[m3] ERROR: Non-chromium browsers have failures"; exit 1; }

echo "[m3] Milestone 3 oracle complete. execution_report.json validated."
