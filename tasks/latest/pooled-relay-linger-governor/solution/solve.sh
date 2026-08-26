#!/bin/bash
# Terminal-Bench Canary STRING pooled-relay-linger-governor-oracle
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export PATH="/usr/local/cargo/bin:${PATH}"

rustup default stable >/dev/null 2>&1 || true

patch -p0 --forward --directory=/app/environment/l7/src -i "$ROOT_DIR/patches/l7_lib.patch"
patch -p0 --forward --directory=/app/environment/p3/src -i "$ROOT_DIR/patches/p3_lib.patch"
patch -p0 --forward --directory=/app/environment/r6/src -i "$ROOT_DIR/patches/r6_lib.patch"
patch -p0 --forward --directory=/app/environment/k4/src -i "$ROOT_DIR/patches/k4_lib.patch"

/usr/local/cargo/bin/cargo build --release --locked --manifest-path /app/environment/Cargo.toml
install -m 0755 /app/environment/target/release/relayctl /app/bin/relayctl

test -x /app/bin/relayctl
