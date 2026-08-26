#!/bin/bash
# Remove any build artifacts and intermediate output files.
# Run this before rebuilding when the output directory needs a clean state.
set -euo pipefail

echo "[clear_scratch] removing build artifacts..."
rm -rf /app/environment/target

echo "[clear_scratch] removing intermediate output files..."
rm -f /app/output/legacy_record_bundle.json
rm -rf /app/output/groups

echo "[clear_scratch] done. Run build_all.sh to rebuild."
