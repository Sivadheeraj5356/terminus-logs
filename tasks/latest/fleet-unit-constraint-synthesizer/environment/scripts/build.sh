#!/bin/bash
set -euo pipefail
ROOT="/app/environment"
mkdir -p /app/bin /app/output /tmp/fleet_stage
cd "$ROOT/fe-core"
cargo build --release --offline --locked
cp target/release/fe_run /app/bin/fe_run
cd "$ROOT/go"
go build -o /app/bin/fleet_emit ./cmd/fleet_emit
go build -o /app/bin/trace_emit ./cmd/trace_emit
