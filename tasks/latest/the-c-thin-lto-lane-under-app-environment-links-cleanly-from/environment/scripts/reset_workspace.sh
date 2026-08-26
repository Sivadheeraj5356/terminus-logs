#!/bin/bash
set -euo pipefail
# shellcheck source=/dev/null
source "$(dirname "$0")/env.sh"
rm -rf "${WORK_ROOT}"
mkdir -p "${GEN_ROOT}" "${LTO_ROOT}" "${OBJ_ROOT}" "${BIN_ROOT}" "${BUILD_ROOT}" /app/output
