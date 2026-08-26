#!/bin/bash
# Terminal-Bench Canary: 4a9f2c8e-1b3d-47a0-9e5c-6f7d8a2b1c4e
# Oracle solution for legacy-record-decoder.
# Applies three coordinated source fixes, rebuilds, and runs xscope.
set -euo pipefail

ENV=/app/environment

echo "[oracle] applying fixes A, B, C..."
python3 /solution/apply_fixes.py

echo "[oracle] rebuilding workspace..."
"$ENV/scripts/build_all.sh"

echo "[oracle] running xscope to generate bundle..."
mkdir -p /app/output
"$ENV/tools/bin/xscope" \
    --all-samples \
    --bundle-out /app/output/legacy_record_bundle.json \
    --fixtures-dir "$ENV/fixtures"

echo "[oracle] bundle written to /app/output/legacy_record_bundle.json"
