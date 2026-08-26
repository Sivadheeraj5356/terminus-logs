#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
make -C "$APP_ROOT" -j"${BUILD_JOBS:-2}" all
