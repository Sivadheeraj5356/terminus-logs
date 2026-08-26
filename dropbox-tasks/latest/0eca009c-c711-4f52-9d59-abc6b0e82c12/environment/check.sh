#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
cargo build --release --locked --offline
mkdir -p /app/bin
install -m 0755 /app/target/release/forest-audit /app/bin/forest-audit
