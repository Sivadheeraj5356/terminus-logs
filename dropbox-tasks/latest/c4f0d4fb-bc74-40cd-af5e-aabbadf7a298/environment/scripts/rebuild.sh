#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
cargo build --workspace --release --locked 2>&1 || cargo build --workspace --release 2>&1
