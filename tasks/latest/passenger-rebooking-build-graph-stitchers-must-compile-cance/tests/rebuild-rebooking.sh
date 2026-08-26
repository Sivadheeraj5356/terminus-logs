#!/bin/bash
set -euo pipefail
GO_BIN="/opt/verifier-bin/go"
if [ ! -x "${GO_BIN}" ]; then
    echo "trusted go toolchain missing" >&2
    exit 1
fi
export PATH="/opt/verifier-bin:${PATH}"
export GOROOT="/usr/local/go"
export CGO_ENABLED=0 GOTOOLCHAIN=local GOPROXY=off GOFLAGS=-mod=mod
export GOCACHE="${GOCACHE:-/tmp/gocache}"
cd /app
"${GO_BIN}" build -o /app/bin/passenger-rebooking-engine ./cmd/passenger-rebooking-engine
