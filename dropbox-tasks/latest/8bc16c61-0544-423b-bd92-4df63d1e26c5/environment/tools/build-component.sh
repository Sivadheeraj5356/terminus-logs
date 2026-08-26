#!/usr/bin/env bash
set -euo pipefail

cd /app
cargo run --quiet -p wit-bindgen-lite -- \
  /app/wit/worker.wit \
  /app/crates/edge-worker/src/generated.rs \
  /app/target/component-build.json \
  /app/target/wasm32-wasip1/release/edge_worker.wasm
cargo build --quiet --release -p edge-worker
