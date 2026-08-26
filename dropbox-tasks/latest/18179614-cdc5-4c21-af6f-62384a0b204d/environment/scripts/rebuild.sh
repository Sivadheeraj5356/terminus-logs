#!/bin/bash
set -euo pipefail
ROOT="/app/environment"
BUILD="$ROOT/build"
export PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$BUILD" /app/output /app/var/massxfer
cd "$ROOT/ot7-core"
cargo build --release --locked
cp "$ROOT/ot7-core/target/release/ot7-core" "$BUILD/ot7-core"
cd "$ROOT"
for cmd in otctl-run otctl-probe otctl-audit otctl-inspect; do
  go build -o "$BUILD/$cmd" "./cmd/$cmd"
done
