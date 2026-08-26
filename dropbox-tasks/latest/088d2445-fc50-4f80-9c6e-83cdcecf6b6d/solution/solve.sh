#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

ROOT="${DRV_ROOT:-/app/environment}"
OUT="${DRV_OUT:-/app/output}"
BUILD="${DRV_BUILD_DIR:-/app/build}"
APP_ROOT="$(dirname "$ROOT")"

patch -p1 -d "$APP_ROOT" < patches/all-fixes.patch

chmod +x "$ROOT/build.sh" "$ROOT/tools/hs_run.sh"
export DRV_ROOT="$ROOT" DRV_OUT="$OUT" DRV_BUILD_DIR="$BUILD"
"$ROOT/tools/hs_run.sh" --all-lanes --rotations "$ROOT/docs/rot_d.toml"
"$ROOT/tools/hs_run.sh" --all-lanes --rotations "$ROOT/docs/rot_d.toml" --warm
