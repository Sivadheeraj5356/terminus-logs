#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
make -C "$APP_ROOT" -j"${BUILD_JOBS:-2}" bin/policyc
"$APP_ROOT/bin/policyc" --source "$APP_ROOT/policy" --output "$APP_ROOT/runtime/pam.d"
