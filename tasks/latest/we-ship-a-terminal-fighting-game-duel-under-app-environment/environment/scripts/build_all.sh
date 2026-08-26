#!/bin/bash
set -euo pipefail
cd /app/environment
mkdir -p bin
cargo build --release
install -m 0755 target/release/duel bin/duel
