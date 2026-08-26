#!/usr/bin/env bash
set -euo pipefail
ROOT="/app/environment"
BUILD="${ROOT}/build"
mkdir -p "${BUILD}"
cmake -S "${ROOT}" -B "${BUILD}" -DCMAKE_BUILD_TYPE=Release
cmake --build "${BUILD}" -j"$(nproc)"
