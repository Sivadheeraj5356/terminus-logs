#!/usr/bin/env bash
set -euo pipefail
ROOT="${WG_ENV_ROOT:-/app/environment}"
cd "$ROOT"
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
install -d /app/bin
install -m 0755 build/wg_run /app/bin/wg_run
