#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$ROOT_DIR/engine.cpp" /app/environment/tools/q5_driver/src/engine.cpp
cp "$ROOT_DIR/raw_io.cpp" /app/environment/support/raw_io.cpp
