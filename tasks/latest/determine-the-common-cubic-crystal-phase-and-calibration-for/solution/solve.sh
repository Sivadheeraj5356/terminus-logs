#!/bin/bash
set -euo pipefail
cp /solution/indexer.rs /app/src/indexer.rs
cd /app
cargo test --offline
cargo build --offline --release
mkdir -p /app/bin
cp target/release/cubic-index /app/bin/cubic-index
/app/bin/cubic-index --study /app/examples/sample.study --output /app/result.json
cmp /app/result.json /app/examples/sample.expected.json
