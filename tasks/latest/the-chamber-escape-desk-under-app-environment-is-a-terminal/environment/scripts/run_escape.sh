#!/usr/bin/env bash
set -euo pipefail

ROOT="/app/environment"
BIN="/app/bin/desk_k"
OUT="/app/output/route_manifest.json"

mkdir -p /app/output /app/bin

cd "$ROOT"
CARGO_TARGET_DIR=/app/.cargo-target cargo build --release --locked -p desk_k
cp /app/.cargo-target/release/desk_k "$BIN"

bash "$ROOT/scripts/stop_escape.sh" || true
bash "$ROOT/svc/chamberd.sh"

"$BIN" --config "$ROOT/config/runner.toml" --output "$OUT"
