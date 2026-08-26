#!/usr/bin/env bash
set -euo pipefail
PROFILE="${PROFILE:-release}"
BUILD_DIR="${1:-/app/work/build}"
cmake -S /app/environment/compile -B "${BUILD_DIR}" -DCMAKE_BUILD_TYPE=Release -G Ninja
ninja -C "${BUILD_DIR}" matrix_app
