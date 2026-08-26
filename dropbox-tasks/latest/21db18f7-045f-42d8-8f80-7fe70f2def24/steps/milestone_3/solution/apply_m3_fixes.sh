#!/bin/bash
# Apply milestone 3 executor.js fixes (idempotent, surgical patches only).
set -euo pipefail

EXECUTOR_JS="/app/lib/executor.js"

# Check if already patched
if grep -q "FROM test_runs" "$EXECUTOR_JS" && grep -q "parent_session_id IS NULL" "$EXECUTOR_JS"; then
  echo "[m3] executor.js already patched"
  exit 0
fi

echo "[m3] Patching executeplan() to delete stale results..."

python3 - "$EXECUTOR_JS" << 'PYEOF'
import sys
filepath = sys.argv[1]
with open(filepath, 'r') as f:
    src = f.read()

# Fix 1: Add DELETE statement before inserting new results
src = src.replace(
    "async function executeplan(plan, db) {\n"
    "  // Re-run support appends rows; session-scoped result handling may need review.\n"
    "\n"
    "  for (const project of plan.projects) {",

    "async function executeplan(plan, db) {\n"
    "  // Clear previous non-interrupted results for this session before inserting new ones.\n"
    "  // Interrupted rows are preserved as a historical record.\n"
    "  db.run('DELETE FROM execution_results WHERE planned_session_id = ? AND interrupted = 0', [plan.session_id]);\n"
    "\n"
    "  for (const project of plan.projects) {"
)

with open(filepath, 'w') as f:
    f.write(src)

print("Fix 1: DELETE statement added to executeplan().")
PYEOF

echo "[m3] Patching failure detection to consult filtered test_runs history..."

python3 - "$EXECUTOR_JS" << 'PYEOF'
import sys
filepath = sys.argv[1]
with open(filepath, 'r') as f:
    src = f.read()

src = src.replace(
    "      const history = db.exec(`\n"
    "        SELECT status FROM test_runs\n"
    "        WHERE spec_file = ? AND browser = ?\n"
    "      `, [spec, project.browser]);\n"
    "      let failCount = 0;\n"
    "      if (history.length && history[0].values) {\n"
    "        for (const [runStatus] of history[0].values) {\n"
    "          if (runStatus === 'failed') failCount++;\n"
    "        }\n"
    "      }\n"
    "      const isFailing = failCount > 0;\n"
    "      const status = isFailing ? 'failed' : 'passed';",

    "      const history = db.exec(`\n"
    "        SELECT status FROM test_runs\n"
    "        WHERE spec_file = ? AND browser = ?\n"
    "          AND deleted = 0 AND parent_session_id IS NULL\n"
    "      `, [spec, project.browser]);\n"
    "      let failCount = 0;\n"
    "      let passCount = 0;\n"
    "      if (history.length && history[0].values) {\n"
    "        for (const [runStatus] of history[0].values) {\n"
    "          if (runStatus === 'failed') failCount++;\n"
    "          else if (runStatus === 'passed') passCount++;\n"
    "        }\n"
    "      }\n"
    "      const isFailing = failCount > passCount;\n"
    "      const status = isFailing ? 'failed' : 'passed';"
)

with open(filepath, 'w') as f:
    f.write(src)

print("Fix 2: failure simulation now queries filtered test_runs history.")
PYEOF

echo "[m3] Patching aggregateResults() to filter interrupted rows..."

python3 - "$EXECUTOR_JS" << 'PYEOF'
import sys
filepath = sys.argv[1]
with open(filepath, 'r') as f:
    src = f.read()

# Fix 3: Add interrupted = 0 filter to WHERE clause
src = src.replace(
    "  const results = db.exec(`\n"
    "    SELECT spec_file, browser, status, retry_count, interrupted\n"
    "    FROM execution_results\n"
    "    WHERE planned_session_id = ?\n"
    "    ORDER BY spec_file ASC, browser ASC\n"
    "  `, [sessionId]);",

    "  const results = db.exec(`\n"
    "    SELECT spec_file, browser, status, retry_count, interrupted\n"
    "    FROM execution_results\n"
    "    WHERE planned_session_id = ? AND interrupted = 0\n"
    "    ORDER BY spec_file ASC, browser ASC\n"
    "  `, [sessionId]);"
)

with open(filepath, 'w') as f:
    f.write(src)

print("Fix 3: interrupted = 0 filter added to aggregateResults().")
PYEOF

echo "[m3] Patching failure records to include browser field..."

python3 - "$EXECUTOR_JS" << 'PYEOF'
import sys
filepath = sys.argv[1]
with open(filepath, 'r') as f:
    src = f.read()

# Fix 4: Add browser field to failure records
src = src.replace(
    "      // Failure detail — fields added incrementally during v2.0/v2.1\n"
    "      failures.push({\n"
    "        spec_file: specFile,\n"
    "        // browser field was added to the schema in v2.1\n"
    "        retry_count: retryCount,\n"
    "        status,\n"
    "      });",

    "      // Failure detail — fields added incrementally during v2.0/v2.1\n"
    "      failures.push({\n"
    "        spec_file: specFile,\n"
    "        browser: browser,\n"
    "        retry_count: retryCount,\n"
    "        status,\n"
    "      });"
)

with open(filepath, 'w') as f:
    f.write(src)

print("Fix 4: browser field added to failure records.")
PYEOF

# Verify all patches
grep -q "DELETE FROM execution_results WHERE planned_session_id = ? AND interrupted = 0" "$EXECUTOR_JS" || { echo "[m3] ERROR: DELETE not found"; exit 1; }
grep -q "FROM test_runs" "$EXECUTOR_JS" || { echo "[m3] ERROR: test_runs history query not found"; exit 1; }
grep -q "deleted = 0 AND parent_session_id IS NULL" "$EXECUTOR_JS" || { echo "[m3] ERROR: history filters not found"; exit 1; }
grep -q "WHERE planned_session_id = ? AND interrupted = 0" "$EXECUTOR_JS" || { echo "[m3] ERROR: interrupted filter not found"; exit 1; }
grep -q "browser: browser," "$EXECUTOR_JS" || { echo "[m3] ERROR: browser field not found"; exit 1; }

echo "[m3] All patches applied successfully."
