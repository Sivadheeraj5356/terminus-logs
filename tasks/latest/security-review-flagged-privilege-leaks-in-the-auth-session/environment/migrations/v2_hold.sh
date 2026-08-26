#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SAMPLES="$ROOT/samples/raw_bytes"
HOLD="$ROOT/samples/.v2_hold"
BAK="$SAMPLES/.bak"
OUT_MARK="/app/output/recovery.marker"

mkdir -p /app/output

if [[ "${1:-}" == "--recover" ]]; then
  mkdir -p "$SAMPLES"
  if [[ -d "$HOLD" ]]; then
    cp -a "$HOLD"/. "$SAMPLES"/ 2>/dev/null || true
    rm -rf "$HOLD"
  fi
  if [[ -d "$BAK" ]]; then
    cp -a "$BAK"/. "$SAMPLES"/
  fi
  printf 'ok\n' > "$OUT_MARK"
  exit 0
fi

# Destructive: park samples behind hold (except .bak)
mkdir -p "$HOLD"
shopt -s nullglob
for f in "$SAMPLES"/*; do
  base="$(basename "$f")"
  if [[ "$base" == ".bak" ]]; then
    continue
  fi
  mv "$f" "$HOLD"/
done
printf 'held\n' > "$OUT_MARK"
