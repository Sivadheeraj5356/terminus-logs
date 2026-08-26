#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
LAB_ROOT="${1:-$APP_ROOT/work/probe}"
"$APP_ROOT/scripts/new-lab.sh" "$LAB_ROOT" >/dev/null
"$APP_ROOT/bin/authctl" probe-recovery --root "$LAB_ROOT" --user alice --secret main-token
