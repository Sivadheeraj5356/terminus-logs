#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/usr/local/go/bin:/app/bin:${PATH}"
export CGO_ENABLED=0
cp "${SCRIPT_DIR}/files/internal/boiloff/boiloff.go" "${APP_ROOT}/internal/boiloff/boiloff.go"
cd "${APP_ROOT}"
/app/scripts/build.sh
test -x /app/bin/lng-boiloff-reconciler
