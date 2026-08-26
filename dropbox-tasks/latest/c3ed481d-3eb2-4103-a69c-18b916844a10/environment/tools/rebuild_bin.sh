#!/bin/bash
set -euo pipefail
export CARGO_HOME="${CARGO_HOME:-/opt/cargo}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/cargo-target}"
export PATH="/usr/local/cargo/bin:/opt/verifier/bin:${PATH}"
cargo build --release --manifest-path /app/environment/Cargo.toml
mkdir -p /app/bin
cp "${CARGO_TARGET_DIR}/release/lane_matrix" /app/bin/lane_matrix
