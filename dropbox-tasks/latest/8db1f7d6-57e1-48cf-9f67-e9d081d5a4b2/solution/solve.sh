#!/bin/bash
set -euo pipefail
export RUST_BACKTRACE=0
export PATH="/usr/local/cargo/bin:${PATH}"
export CARGO_HOME="/usr/local/cargo"
export CARGO_NET_OFFLINE=true
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/replay_tool_src/src /app/bin
cp "${ROOT}/Cargo.toml" /app/replay_tool_src/Cargo.toml
cp -R "${ROOT}/src/." /app/replay_tool_src/src/
cd /app/replay_tool_src
cargo build --release --quiet 2>&1
cp -f "target/release/replay_tool" "/app/bin/replay_tool"
chmod +x "/app/bin/replay_tool"
[ -x "/app/bin/replay_tool" ] || { echo "Binary missing" >&2; exit 1; }
/app/bin/replay_tool /app/task_file
