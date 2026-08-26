#!/bin/bash
# Apply milestone 2 planner.js fixes (idempotent).
set -euo pipefail

PLANNER_JS="/app/lib/planner.js"

if grep -q "MAX(id)" "$PLANNER_JS" && grep -q "retries: projectConfig.retry_on_failure" "$PLANNER_JS" && grep -q "total_specs: flakyEntries.length" "$PLANNER_JS"; then
  echo "[m2] planner.js already patched"
  exit 0
fi

echo "[m2] Patching getBrowserProjects() and buildProjectEntry()..."

python3 - "$PLANNER_JS" << 'PYEOF'
import sys
filepath = sys.argv[1]
with open(filepath, 'r') as f:
    src = f.read()

src = src.replace("MIN(id)", "MAX(id)")
src = src.replace(
    "    // Retry count — set during the initial multi-browser implementation\n"
    "    retries: 2,",
    "    retries: projectConfig.retry_on_failure,"
)
src = src.replace(
    "    total_specs: new Set(flakyEntries.map((entry) => entry.spec_file)).size,",
    "    total_specs: flakyEntries.length,"
)

with open(filepath, 'w') as f:
    f.write(src)

print("Both patches applied to planner.js.")
PYEOF

grep -q "MAX(id)" "$PLANNER_JS" || { echo "[m2] ERROR: MAX(id) not found after patch"; exit 1; }
grep -q "retries: projectConfig.retry_on_failure" "$PLANNER_JS" || {
  echo "[m2] ERROR: retries not wired to retry_on_failure after patch"
  exit 1
}
grep -q "total_specs: flakyEntries.length" "$PLANNER_JS" || {
  echo "[m2] ERROR: total_specs must count flaky spec+browser pairs after patch"
  exit 1
}
echo "[m2] planner.js patched"
