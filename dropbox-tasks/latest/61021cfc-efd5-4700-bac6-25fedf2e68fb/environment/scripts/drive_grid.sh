#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-/app/output/pack_trace.json}"
exec /app/environment/tools/rk_pack/rk_pack --matrix --out "$OUT"
