#!/bin/bash
set -euo pipefail
cd /app
export PATH="/usr/local/cargo/bin:${PATH}"
export CARGO_INCREMENTAL=0
cargo build --release --locked
mkdir -p /app/bin
install -m 0755 /app/target/release/assay-ledger /app/bin/assay-ledger
