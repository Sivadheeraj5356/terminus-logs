#!/bin/bash
# Operator helper: copy a scenario tree into a local park workspace for offline review.
set -euo pipefail
cd /app
SRC="${1:-/app/fixtures/scenarios/dept_merge}"
DEST="${2:-/app/state/odip/scenario_park}"
mkdir -p "$DEST"
cp -a "$SRC/." "$DEST/"
echo "parked scenario copy at ${DEST}"
