#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Milestones 1-3 already populated /app/transparency. Install the log auditor.
cp "$SCRIPT_DIR/audit.py" /app/transparency/audit.py
