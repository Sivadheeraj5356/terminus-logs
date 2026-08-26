#!/bin/bash
# Optional env overrides: OUTPUT_DIR, REPLAY_ROOT, TRIM_CYCLES, APPEND_EXPORT
set -euo pipefail
ROOT="${REPLAY_ROOT:-/app/environment}"
OUT="${OUTPUT_DIR:-/app/output}"
export REPLAY_ROOT="$ROOT"
mkdir -p "$OUT"
CYCLES="${TRIM_CYCLES:-2}"
for ((i=1; i<=CYCLES; i++)); do
  export CYCLE="$i"
  /app/bin/volutil run "$OUT"
  export APPEND_EXPORT=1
done
