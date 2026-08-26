#!/bin/bash
# Apply milestone 1 history.js SQL filters (idempotent).
set -euo pipefail

HISTORY_JS="/app/lib/history.js"

if ! grep -q "FROM test_runs" "$HISTORY_JS"; then
  echo "[m1] ERROR: Expected query not found in history.js"
  exit 1
fi

if grep -q "WHERE deleted = 0 AND parent_session_id IS NULL" "$HISTORY_JS"; then
  echo "[m1] history.js already patched"
  exit 0
fi

echo "[m1] Patching getFlakyCounts() to exclude deleted and rerun sessions..."

python3 - "$HISTORY_JS" << 'PYEOF'
import sys
filepath = sys.argv[1]
with open(filepath, 'r') as f:
    src = f.read()

src = src.replace(
    "  // Aggregation scope last reviewed during the v2.0 schema migration.\n"
    "  const results = db.exec(`\n"
    "    SELECT\n"
    "      spec_file,\n"
    "      browser,\n"
    "      SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS fail_count,\n"
    "      SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS pass_count,\n"
    "      COUNT(*) AS total_runs\n"
    "    FROM test_runs\n"
    "    GROUP BY spec_file, browser\n"
    "    ORDER BY fail_count DESC, spec_file DESC\n"
    "  `);",

    "  // Fixed: exclude soft-deleted sessions and rerun/retry sessions\n"
    "  const results = db.exec(`\n"
    "    SELECT\n"
    "      spec_file,\n"
    "      browser,\n"
    "      SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS fail_count,\n"
    "      SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS pass_count,\n"
    "      COUNT(*) AS total_runs\n"
    "    FROM test_runs\n"
    "    WHERE deleted = 0 AND parent_session_id IS NULL\n"
    "    GROUP BY spec_file, browser\n"
    "    ORDER BY fail_count DESC, spec_file ASC\n"
    "  `);"
)

with open(filepath, 'w') as f:
    f.write(src)

print("Patch applied successfully.")
PYEOF

grep -q "WHERE deleted = 0" "$HISTORY_JS" || { echo "[m1] ERROR: deleted filter not found after patch"; exit 1; }
grep -q "AND parent_session_id IS NULL" "$HISTORY_JS" || { echo "[m1] ERROR: parent_session filter not found after patch"; exit 1; }
grep -q "ORDER BY fail_count DESC, spec_file ASC" "$HISTORY_JS" || { echo "[m1] ERROR: tie-break sort not corrected after patch"; exit 1; }
echo "[m1] history.js patched"
