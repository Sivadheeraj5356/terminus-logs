#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p /app/transparency /app/data /app/out
cp "$SCRIPT_DIR/canonical.py" /app/transparency/canonical.py
cp "$SCRIPT_DIR/cli.py" /app/transparency/cli.py
# /app/data/manifest.json is already provided by the Docker image build
# (environment/Dockerfile COPYs data/manifest.json). No re-staging needed.

python3 /app/transparency/cli.py canonicalize /app/data/manifest.json --out /app/out
