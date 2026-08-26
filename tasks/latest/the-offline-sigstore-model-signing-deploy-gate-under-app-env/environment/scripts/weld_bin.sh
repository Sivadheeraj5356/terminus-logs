#!/usr/bin/env bash
set -euo pipefail
ROOT="/app/environment"
SCRATCH="$ROOT/.scratch"
mkdir -p "$SCRATCH" /app/output/stage /app/output "$ROOT/bin"

cd "$ROOT"
go build -o "$ROOT/bin/mxbin" ./cmd/mxbin

"$ROOT/bin/mxbin" fold
"$ROOT/bin/mxbin" bind

printf 'weld_ok scratch=%s\n' "$SCRATCH"
