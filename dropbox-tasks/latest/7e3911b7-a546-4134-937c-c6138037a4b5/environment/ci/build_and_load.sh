#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${TASK_APP_ROOT:-/app}"
cd "${APP_ROOT}"
make -C "${APP_ROOT}" clean
make -C "${APP_ROOT}"
mkdir -p "${APP_ROOT}/output" "${APP_ROOT}/var/snapshots"
"${APP_ROOT}/bin/nav_matrix"
test -s "${APP_ROOT}/output/nav_audit.json"
