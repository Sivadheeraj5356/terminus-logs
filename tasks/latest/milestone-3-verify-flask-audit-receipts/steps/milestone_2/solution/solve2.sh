#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Milestone 1 artifacts (canonical.py, cli.py) already exist in /app from M1.
cp "$SCRIPT_DIR/keys.py" /app/transparency/keys.py

python3 /app/transparency/cli.py keygen --key-dir /app/keys
python3 /app/transparency/cli.py sign /app/data/manifest.json --key-dir /app/keys --out /app/out
python3 /app/transparency/cli.py verify /app/data/manifest.json --key-dir /app/keys --sig /app/out/manifest.sig
