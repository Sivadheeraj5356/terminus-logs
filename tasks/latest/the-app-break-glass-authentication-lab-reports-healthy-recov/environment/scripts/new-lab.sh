#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
LAB_ROOT="${1:?usage: new-lab.sh LAB_ROOT}"
case "$LAB_ROOT" in
    ""|/|/app|/tests|/solution) echo "refusing unsafe lab root: $LAB_ROOT" >&2; exit 64 ;;
esac
rm -rf -- "$LAB_ROOT"
mkdir -p "$LAB_ROOT/fixtures" "$LAB_ROOT/pam.d"
cp "$APP_ROOT/fixtures/users.db" "$LAB_ROOT/fixtures/users.db"
cp "$APP_ROOT/fixtures/tokens.db" "$LAB_ROOT/fixtures/tokens.db"
cp "$APP_ROOT"/runtime/pam.d/*.conf "$LAB_ROOT/pam.d/"
"$APP_ROOT/bin/authctl" bootstrap --root "$LAB_ROOT"
