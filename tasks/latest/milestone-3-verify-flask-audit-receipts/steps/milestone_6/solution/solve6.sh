#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Milestones 1-5 already populated /app/transparency. Install the entry
# leaf-canonicalizer recovered from the worked examples.
mkdir -p /app/transparency /app/out
cp "$SCRIPT_DIR/entrycanon.py" /app/transparency/entrycanon.py

# Demonstrate the CLI on a shipped worked example.
python3 /app/transparency/entrycanon.py canonicalize \
    --entry /app/transparency/entrylog/examples/entry_01.json \
    --out /app/out/entry_01.canonical.bin
python3 /app/transparency/entrycanon.py signed-input \
    --entry /app/transparency/entrylog/examples/entry_01.json \
    --out /app/out/entry_01.signed_input.bin
