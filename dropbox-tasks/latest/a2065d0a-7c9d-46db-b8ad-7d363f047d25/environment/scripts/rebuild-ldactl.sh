#!/usr/bin/env bash
set -euo pipefail
cd /app
export CARGO_NET_OFFLINE=true
cargo build --offline --release --locked -p ldactl
install -m 0755 /app/target/release/ldactl /usr/local/bin/ldactl
