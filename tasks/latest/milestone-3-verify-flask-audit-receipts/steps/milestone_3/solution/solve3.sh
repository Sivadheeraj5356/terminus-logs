#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Milestone 1 + 2 artifacts already exist in /app.
cp "$SCRIPT_DIR/log.py" /app/transparency/log.py
cp "$SCRIPT_DIR/app.py" /app/transparency/app.py

python3 "$SCRIPT_DIR/demo3.py"
