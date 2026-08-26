#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${DRV_BUILD_DIR:-/app/build}"
mkdir -p "$OUT_DIR"

cd "$ROOT"
go build -o "$OUT_DIR/hs_drv" ./cmd/hs_drv
