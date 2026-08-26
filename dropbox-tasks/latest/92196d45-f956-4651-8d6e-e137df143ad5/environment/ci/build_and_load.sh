#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${TASK_APP_ROOT:-/app}"
cd "${APP_ROOT}"

make -C "${APP_ROOT}" clean
make -C "${APP_ROOT}"
mkdir -p "${APP_ROOT}/output" "${APP_ROOT}/var/snapshots"
"${APP_ROOT}/bin/plan_matrix"
test -s "${APP_ROOT}/output/plan_audit.json"
