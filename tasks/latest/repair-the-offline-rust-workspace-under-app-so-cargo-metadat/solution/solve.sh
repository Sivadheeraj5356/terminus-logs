#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/.cargo/config.toml" /app/.cargo/config.toml
cp "$SCRIPT_DIR/src/lib.rs" /app/crates/metacycle-core/src/lib.rs
cp "$SCRIPT_DIR/src/version.rs" /app/crates/metacycle-core/src/version.rs
cp "$SCRIPT_DIR/metrics-macros/Cargo.toml" /app/crates/metrics-macros/Cargo.toml
cp "$SCRIPT_DIR/metrics-cli/Cargo.toml" /app/crates/metrics-cli/Cargo.toml
cp "$SCRIPT_DIR/metrics-core-lib.rs" /app/crates/metrics-core/src/lib.rs
cp "$SCRIPT_DIR/metrics-cli-main.rs" /app/crates/metrics-cli/src/main.rs
cp "$SCRIPT_DIR/metacycle-cli-main.rs" /app/crates/metacycle-cli/src/main.rs
cp "$SCRIPT_DIR/assets/Cargo.lock" /app/Cargo.lock
cp "$SCRIPT_DIR/build-release.sh" /app/scripts/build-release.sh
chmod 0755 /app/scripts/build-release.sh /app/scripts/healthcheck.sh

bash /app/scripts/build-release.sh
