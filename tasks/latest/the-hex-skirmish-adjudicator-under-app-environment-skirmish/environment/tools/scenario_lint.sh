#!/usr/bin/env bash
set -euo pipefail
# Lightweight presence check for scenario files during local editing.
for f in "$@"; do
  [[ -f "$f" ]] || { echo "missing $f"; exit 1; }
  grep -q '"map"' "$f" || { echo "no map in $f"; exit 1; }
done
echo "ok"
