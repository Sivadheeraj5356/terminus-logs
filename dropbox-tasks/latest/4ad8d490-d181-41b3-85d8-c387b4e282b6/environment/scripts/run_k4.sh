#!/bin/bash
set -euo pipefail
ROOT="${K4_ROOT:-/app/environment}"
cd "$ROOT"
if [[ ! -f dist/src/cmd/desk_run.js ]]; then
  bash scripts/build_k4.sh
fi
exec node dist/src/cmd/desk_run.js --env "$ROOT" "$@"
