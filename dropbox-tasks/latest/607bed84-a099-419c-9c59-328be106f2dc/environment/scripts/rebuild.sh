#!/bin/bash
set -euo pipefail
ROOT="/app/environment"
BUILD="$ROOT/build"
export PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$BUILD" /app/output /app/var/basinspan
cd "$ROOT/bs7-core"
cargo build --release --locked
cp "$ROOT/bs7-core/target/release/bs7-core" "$BUILD/bs7-core"
cd "$ROOT"
for cmd in basinspan-run basinspan-probe basinspan-audit basinspan-inspect; do
  go build -o "$BUILD/$cmd" "./cmd/$cmd"
done
