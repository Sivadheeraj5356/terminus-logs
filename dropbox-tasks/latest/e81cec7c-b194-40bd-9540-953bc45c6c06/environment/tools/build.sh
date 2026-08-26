#!/bin/bash
set -euo pipefail

BUILD_DIR="/app/build"
JOBS="$(nproc 2>/dev/null || echo 2)"
mkdir -p "${BUILD_DIR}" /app/bin
cmake -S /app -B "${BUILD_DIR}" -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build "${BUILD_DIR}" --target cryoready -j"${JOBS}"
cp "${BUILD_DIR}/cryoready" /app/bin/cryoready
chmod +x /app/bin/cryoready
