#!/bin/bash
set -euo pipefail
ROOT=/app
WORK="$ROOT/work"
mkdir -p "$WORK" "$ROOT/output"

bash "$ROOT/driver/compile_cores.sh"

"$WORK/sep_tool" \
  "$ROOT/data/annex_slice36" \
  "$ROOT/data/bands/profiles" \
  "$WORK/cut.json"

export CUT_CTX="$WORK/cut.json"
"$WORK/fold_tool" \
  "$ROOT/data/annex_slice36" \
  "$ROOT/data/bands/profiles" \
  "$WORK/pack.json"

"$WORK/tie_tool" \
  "$ROOT/data/annex_slice36" \
  "$WORK" \
  "$ROOT/output/ghost_seal.json"

echo "wrote $ROOT/output/ghost_seal.json"
