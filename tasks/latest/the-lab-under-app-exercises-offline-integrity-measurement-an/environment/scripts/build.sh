#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
cd "$APP_DIR"

mkdir -p bin output

go build -trimpath -buildvcs=false -o bin/loader ./cmd/loader
go build -trimpath -buildvcs=false -o bin/reconcile ./cmd/reconcile

( cd hook && cargo build --release --offline --quiet )
HOOK=hook/target/release/hook

bin/loader \
    --authority data/authority \
    --workload data/workload.json \
    --program output/program.json \
    --jobs output/jobs.txt

"$HOOK" \
    --program output/program.json \
    --jobs output/jobs.txt \
    --manifest data/manifest.json \
    --traces output/read_traces.json \
    --log output/measure_log.json

bin/reconcile \
    --program output/program.json \
    --traces output/read_traces.json \
    --log output/measure_log.json \
    --manifest data/manifest.json \
    --out output/integrity_report.json

echo "build: wrote output/program.json output/jobs.txt output/read_traces.json output/measure_log.json output/integrity_report.json"
