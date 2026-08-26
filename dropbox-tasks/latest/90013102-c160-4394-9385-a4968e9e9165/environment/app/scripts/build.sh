#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p bin /output /logs/agent state/spool
go test ./...
go build -o bin/proxy-local ./cmd/proxy-local
go build -o bin/backend-capture ./cmd/backend-capture
go build -o bin/spool-inspect ./cmd/spool-inspect
echo "build ok"
