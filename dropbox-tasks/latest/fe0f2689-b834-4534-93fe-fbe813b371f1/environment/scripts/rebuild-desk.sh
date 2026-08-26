#!/usr/bin/env bash
set -euo pipefail

cd /app/environment
CARGO_TARGET_DIR=/app/.cargo-target cargo build --release --locked -p desk_k
cp /app/.cargo-target/release/desk_k /app/bin/desk_k
