#!/bin/bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/usr/bin:${PATH}"
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export CARGO_INCREMENTAL=0
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/verifier-cargo-target}"

cd /app
mkdir -p "${CARGO_TARGET_DIR}" /app/bin /app/output /app/state
cargo build --release --locked --offline
BUILT="${CARGO_TARGET_DIR}/release/haar-denoiser"
test -x "${BUILT}"
if cp -f "${BUILT}" /app/bin/haar-denoiser 2>/dev/null; then
  chmod 0755 /app/bin/haar-denoiser || true
else
  cp -f "${BUILT}" /tmp/haar-denoiser
  chmod 0755 /tmp/haar-denoiser
  ln -sfn /tmp/haar-denoiser /app/bin/haar-denoiser 2>/dev/null || export PATH="/tmp:${PATH}"
fi
test -x /app/bin/haar-denoiser || test -x /tmp/haar-denoiser
