#!/bin/bash
# Build all workspace crates and install xscope to /app/environment/tools/.
set -euo pipefail

cd /app/environment

# Ensure binary fixtures are present (regenerate if missing).
echo "[build_all] generating fixtures..."
python3 scripts/gen_fixtures.py 2>&1

# Reuse the pre-built dependency artifacts from the Docker build stage.
# CARGO_TARGET_DIR is set in the Dockerfile ENV so incremental rebuilds
# after source edits do not need to recompile dependencies from scratch.
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/app/environment/target}"

echo "[build_all] building workspace (offline, reusing baked registry)..."
cargo build --release --workspace --offline 2>&1

BIN_DIR=/app/environment/tools/bin
mkdir -p "$BIN_DIR"
cp "${CARGO_TARGET_DIR}/release/xscope" "$BIN_DIR/xscope"
chmod +x "$BIN_DIR/xscope"

echo "[build_all] xscope installed to $BIN_DIR/xscope"
