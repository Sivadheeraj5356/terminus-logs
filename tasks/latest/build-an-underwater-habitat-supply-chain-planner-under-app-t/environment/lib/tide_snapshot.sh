#!/usr/bin/env bash
set -euo pipefail
# Ingest module to build: tide snapshot acts.
# Args: $1 = parsed mission JSON, $2 = mission_hash
# Emit tide-snapshot JSON on stdout per /app/docs/tide-snapshot.md,
# /app/docs/tide-offset-windows.md, and /app/docs/wave-scaling.md.
echo "habitat-resupply: tide_snapshot capability not built yet — build per /app/docs/tide-snapshot.md" >&2
exit 1
