#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p /app/task_file/src /app/task_file/bin /app/task_file/output
cp "${script_dir}/token_audit.go" /app/task_file/src/token_audit.go
go build -o /app/task_file/bin/token_audit /app/task_file/src/token_audit.go

/app/task_file/bin/token_audit \
    --input /app/task_file/input/public_exchange.txt \
    --output /app/task_file/output/report.json
