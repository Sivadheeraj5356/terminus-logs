#!/bin/bash
set -euo pipefail
export RUST_BACKTRACE=0
export PATH="/usr/local/cargo/bin:${PATH}"
export CARGO_NET_OFFLINE=true
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
if [ ! -f "${ROOT}/src/main.rs" ]; then
  ROOT="/solution"
fi
mkdir -p /app/bin
for f in main.rs types.rs config.rs parse.rs shards.rs ops.rs replay.rs output.rs; do
  cp -f "${ROOT}/src/${f}" "/app/desiccator_tray_src/src/${f}"
done
cd /app/desiccator_tray_src
cargo build --release
install -m 755 target/release/desiccator_tray /app/bin/desiccator_tray
[ -x /app/bin/desiccator_tray ] || { echo "Binary missing after build" >&2; exit 1; }
