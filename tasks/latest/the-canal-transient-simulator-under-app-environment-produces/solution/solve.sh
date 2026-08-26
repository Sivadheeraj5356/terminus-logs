#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

echo "[solve] installing corrected lockctl modules"
cp -f "$ROOT_DIR/files/src/storage_curve.cpp" /app/environment/src/storage_curve.cpp
cp -f "$ROOT_DIR/files/src/flow_laws.cpp" /app/environment/src/flow_laws.cpp
cp -f "$ROOT_DIR/files/src/engine.cpp" /app/environment/src/engine.cpp

echo "[solve] rebuilding lockctl"
cmake -S /app/environment -B /app/environment/build
cmake --build /app/environment/build --target lockctl -j2

BIN=/app/environment/build/lockctl
OUT=/app/environment/output
mkdir -p "$OUT"
rm -f "$OUT"/*.json

CASE=/app/environment/data/case_demo.json

echo "[solve] clean full run"
"$BIN" run --case "$CASE" --output "$OUT/clean.json"

echo "[solve] partial snapshot run"
"$BIN" run --case "$CASE" --stop-at 1800 \
  --output "$OUT/partial.json" --snapshot-out "$OUT/snap.json"

echo "[solve] restore to completion"
"$BIN" restore --case "$CASE" --snapshot "$OUT/snap.json" \
  --output "$OUT/restored.json"

echo "[solve] verifying restored completion"
python3 - <<'PY'
import json
from pathlib import Path
clean=json.loads(Path("/app/environment/output/clean.json").read_text())
restored=json.loads(Path("/app/environment/output/restored.json").read_text())
assert restored["completed"] is True
assert restored["simulated_until_s"] == clean["simulated_until_s"]
assert restored["schema_version"] == 4
# Final sample conservation should be close
cs=clean["samples"][-1]["conservation"]
rs=restored["samples"][-1]["conservation"]
for k in cs:
    if abs(cs[k]-rs[k]) > 1.0:
        raise SystemExit(f"final conservation drift on {k}: {cs[k]} vs {rs[k]}")
print("restore_continuity_ok")
PY

echo "[solve] audit"
"$BIN" audit --case "$CASE" --ledger "$OUT/clean.json"

echo "[solve] completed successfully"
