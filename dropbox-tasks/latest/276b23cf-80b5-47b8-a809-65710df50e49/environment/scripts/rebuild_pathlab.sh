#!/usr/bin/env bash
set -euo pipefail
exec /usr/local/cargo/bin/cargo build --release --locked --manifest-path /app/environment/Cargo.toml
