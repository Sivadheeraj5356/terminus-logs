#!/usr/bin/env bash
set -euo pipefail
ROOT="${RUNTIME_ROOT:-${TB3_APP_ROOT:-/app}}"
rm -rf "${ROOT}/state" "${ROOT}/output" "${ROOT}/cache"
mkdir -p "${ROOT}/state/checkpoints" "${ROOT}/output" "${ROOT}/cache"
echo "clean_state: cleared state/output/cache under ${ROOT}"
