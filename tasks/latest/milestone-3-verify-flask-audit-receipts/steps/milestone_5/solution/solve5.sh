#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Milestones 1-4 already populated /app/transparency. Install the trust-graph analyzer.
cp "$SCRIPT_DIR/trustgraph.py" /app/transparency/trustgraph.py
