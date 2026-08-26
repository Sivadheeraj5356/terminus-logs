#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DRV_ROOT="${DRV_ROOT:-$ROOT}"
export DRV_OUT="${DRV_OUT:-/app/output}"
export DRV_BUILD_DIR="${DRV_BUILD_DIR:-/app/build}"

"$DRV_ROOT/build.sh"

exec "$DRV_BUILD_DIR/hs_drv" "$@"
