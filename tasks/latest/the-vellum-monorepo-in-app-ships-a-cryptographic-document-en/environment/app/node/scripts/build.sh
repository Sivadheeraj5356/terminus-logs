#!/usr/bin/env bash
# Stage the Node package contents: sources, declarations, and the native CLI.
# Usage: build.sh <source-root> <stage-dir> <generated-dir> <features>
set -euo pipefail

SRC="$1"
STAGE="$2"
GENERATED="$3"
FEATURES="${4:-}"

mkdir -p "$STAGE/bin" "$STAGE/decl"
cp "$SRC/node/src/index.js" "$STAGE/index.js"
cp "$SRC/node/package.json" "$STAGE/package.json"
cp "$SRC/generated/checked-in/node_decl.txt" "$STAGE/decl/node_decl.txt"

export CARGO_TARGET_DIR="$SRC/node/native-target"
cargo build --release --manifest-path "$SRC/Cargo.toml" -p vellum-cli --no-default-features
cp "$SRC/node/native-target/release/vellum-cli" "$STAGE/bin/vellum-cli"
