#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
CARGO_BIN="${CARGO_BIN:-/usr/local/cargo/bin/cargo}"
"$CARGO_BIN" build --release --locked -p k7
install -m 0755 target/release/k7 /app/bin/k7
