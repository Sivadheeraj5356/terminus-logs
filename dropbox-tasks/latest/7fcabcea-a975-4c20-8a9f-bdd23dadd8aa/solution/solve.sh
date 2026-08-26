#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
patch -p1 -d /app < "$ROOT_DIR/repair.patch"
cargo build --release --locked --manifest-path /app/Cargo.toml
install -m 0755 /app/target/release/lora-gate /usr/local/bin/lora-gate
