#!/usr/bin/env bash
set -euo pipefail
SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SOLUTION_DIR/apply_fixes.sh"
modgate --manifest /app/data/manifest.json --out /app/output
