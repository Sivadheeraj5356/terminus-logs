#!/bin/bash
set -euo pipefail
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SRC_DIR/main.rs" /app/src/main.rs
cd /app
make
