#!/bin/bash
# Run xscope against individual sample groups for manual inspection.
set -euo pipefail

XSCOPE=/app/environment/tools/bin/xscope
FIXTURES=/app/environment/fixtures
OUT_DIR=/app/output/groups

mkdir -p "$OUT_DIR"

for group in set_a set_b; do
    echo "[drive_suite] processing $group ..."
    "$XSCOPE" \
        --group "$group" \
        --bundle-out "$OUT_DIR/${group}_bundle.json" \
        --fixtures-dir "$FIXTURES"
    echo "[drive_suite] wrote $OUT_DIR/${group}_bundle.json"
done

echo "[drive_suite] done. Use build_all.sh + xscope --all-samples for the graded bundle."
