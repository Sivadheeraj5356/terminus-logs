#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
cargo build --locked
install -m 0755 target/debug/piezo-audit /app/environment/bin/piezo-audit
