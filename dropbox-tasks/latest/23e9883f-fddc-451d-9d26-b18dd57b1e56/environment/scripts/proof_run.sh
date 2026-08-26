#!/bin/bash
set -euo pipefail
ROOT="${1:-/app}"
if [[ ! -x "$ROOT/bin/mode_seal" ]]; then
  bash "$ROOT/scripts/build_engine.sh" "$ROOT"
fi
exec "$ROOT/bin/mode_seal" "$ROOT"
