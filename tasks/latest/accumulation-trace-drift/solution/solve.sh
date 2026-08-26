#!/bin/bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:${PATH}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd /app/environment
patch -p1 < "${ROOT_DIR}/oracle.patch"

CARGO_TARGET_DIR=/app/environment/target \
  /usr/local/cargo/bin/cargo build --release --offline --locked --manifest-path /app/environment/Cargo.toml
