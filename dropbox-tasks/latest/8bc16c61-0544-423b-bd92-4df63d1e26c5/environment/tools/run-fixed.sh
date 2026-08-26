#!/usr/bin/env bash
set -euo pipefail

cd /app
/app/tools/build-component.sh >/tmp/component-build.log
mkdir -p /app/reports
cargo run --quiet -p host-runner -- \
  --component /app/target/wasm32-wasip2/release/edge_worker.wasm \
  --fixtures /app/fixtures \
  --mode wasi-error-cleanup \
  --report /app/reports/fault-fixed.json
