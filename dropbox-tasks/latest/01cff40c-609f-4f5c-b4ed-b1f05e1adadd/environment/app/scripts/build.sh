#!/usr/bin/env bash
set -euo pipefail
cd /app
export PATH="/usr/local/go/bin:${PATH}"
export CGO_ENABLED=1
mkdir -p /app/bin
go build -mod=vendor -o /app/bin/fert-ingest ./cmd/fert-ingest
go build -mod=vendor -o /app/bin/fert-export ./cmd/fert-export
