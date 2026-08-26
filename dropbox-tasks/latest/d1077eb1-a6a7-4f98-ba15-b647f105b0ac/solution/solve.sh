#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="${SCRIPT_DIR}/oracle"

cp "${ORACLE_DIR}/CMakeLists.txt" /app/environment/CMakeLists.txt
cp -R "${ORACLE_DIR}/include/." /app/environment/include/
cp -R "${ORACLE_DIR}/src/." /app/environment/src/

cmake -S /app/environment -B /app/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/app
cmake --build /app/build -j"$(nproc)"
cmake --install /app/build
mkdir -p /app/output
/app/bin/hann_energy_audit --pack /app/inputs/pack.json --out /app/output/report.json
