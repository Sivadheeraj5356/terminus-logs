#!/usr/bin/env bash
set -euo pipefail
cd /app
mkdir -p /app/bin
export PATH="/usr/local/go/bin:${PATH}"
export GOPROXY="${GOPROXY:-off}"
export GOFLAGS="${GOFLAGS:--mod=vendor}"
go build -o /app/bin/reelseal ./cmd/reelseal
go build -o /app/bin/reelseal-policyapi ./policyapi
