#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/main.rs" /app/tariff/src/main.rs
cd /app/tariff && CARGO_NET_OFFLINE=true cargo build --offline --locked --release
