#!/bin/bash
set -euo pipefail
ROOT="${1:-/app/environment}"
OUT="${2:-/app/bin/cg_xmit}"
mkdir -p "$(dirname "$OUT")"
cd "$ROOT"
export PATH="/usr/local/cargo/bin:/opt/verifier/bin:${PATH}"
export CARGO_HOME="${CARGO_HOME:-/opt/cargo-home}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/target}"
mkdir -p "$CARGO_HOME" "$CARGO_TARGET_DIR"
CARGO_BIN="/usr/local/cargo/bin/cargo"
if [ ! -x "$CARGO_BIN" ]; then
  CARGO_BIN="$(command -v cargo || true)"
fi
if [ -z "${CARGO_BIN}" ] || [ ! -x "$CARGO_BIN" ]; then
  echo "cargo not found" >&2
  exit 3
fi
"$CARGO_BIN" build --offline --release -p drv -q
BIN="$CARGO_TARGET_DIR/release/cg_xmit"
if [ ! -f "$BIN" ]; then
  echo "missing binary: $BIN" >&2
  exit 3
fi
cp -f "$BIN" "$OUT"
chmod +x "$OUT"
echo "wrote $OUT"
