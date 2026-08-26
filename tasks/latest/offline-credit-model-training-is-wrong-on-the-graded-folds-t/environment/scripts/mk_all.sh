#!/bin/bash
set -euo pipefail
cd /app/environment
mkdir -p bin
export PATH="/usr/local/go/bin:/go/bin:${PATH:-}"
export GOPROXY="${GOPROXY:-off}"
export GOSUMDB="${GOSUMDB:-off}"
export GOTOOLCHAIN="${GOTOOLCHAIN:-local}"
export GOFLAGS="${GOFLAGS:--mod=mod}"
export CGO_ENABLED=0
/usr/local/go/bin/go build -o bin/pitctl ./cmd/pitctl
chmod +x bin/pitctl
