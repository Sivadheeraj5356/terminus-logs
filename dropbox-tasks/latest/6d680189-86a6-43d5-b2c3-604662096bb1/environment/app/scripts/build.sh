#!/usr/bin/env bash
set -euo pipefail
cd /app
cargo build --release --locked -p tb3
install -d /app/bin /app/state /app/out
install -m 0755 /app/target/release/gaa-extract /app/bin/gaa-extract

