#!/usr/bin/env bash
# Show the dataset country lookup for a handful of pinned codes.
set -euo pipefail
BIN=/app/crosspay
for cc in JP BH DE AU; do
    "$BIN" country-info --country "$cc" || true
done
