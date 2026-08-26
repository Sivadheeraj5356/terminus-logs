#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export OV_ROOT="$ROOT"
export PATH="/usr/local/go/bin:/opt/verifier/bin:${PATH:-/usr/bin:/bin}"
mkdir -p "$ROOT/tools/ov_probe" "$ROOT/bag" /app/output
bash "$ROOT/q8/legacy.sh" "mode=strict" || true
bash "$ROOT/r4/stub.sh" dig-a || true
bash "$ROOT/t6/decoy.sh" "eng://noop" || true
go build -o "$ROOT/tools/ov_probe/ov_engine" ./tools/ov_probe
chmod +x "$ROOT/tools/ov_probe/ov_probe" "$ROOT/tools/ov_probe/ov_engine"
chmod +x "$ROOT/migrations/rst9.sh" "$ROOT/q8/legacy.sh" "$ROOT/r4/stub.sh" "$ROOT/t6/decoy.sh"
