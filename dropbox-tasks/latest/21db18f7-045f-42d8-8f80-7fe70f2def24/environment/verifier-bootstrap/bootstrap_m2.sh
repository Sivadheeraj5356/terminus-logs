#!/bin/bash
# Verifier-only prerequisite: stable plan generation for milestone 3 verification.
set -euo pipefail

PLANNER_JS="/app/lib/planner.js"

if grep -q "MAX(id)" "$PLANNER_JS" && grep -q "retries: projectConfig.retry_on_failure" "$PLANNER_JS" && grep -q "total_specs: flakyEntries.length" "$PLANNER_JS"; then
  exit 0
fi

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
PYEOF

grep -q "MAX(id)" "$PLANNER_JS" || { echo "[bootstrap-m2] ERROR: MAX(id) missing"; exit 1; }
grep -q "retries: projectConfig.retry_on_failure" "$PLANNER_JS" || { echo "[bootstrap-m2] ERROR: retries wiring missing"; exit 1; }
grep -q "total_specs: flakyEntries.length" "$PLANNER_JS" || { echo "[bootstrap-m2] ERROR: total_specs pair count missing"; exit 1; }
