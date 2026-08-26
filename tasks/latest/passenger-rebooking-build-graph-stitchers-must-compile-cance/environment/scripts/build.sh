#!/bin/bash
set -euo pipefail
export HOME="${HOME:-/home/rebooker}"
export PATH="/usr/local/go/bin:/usr/bin:${PATH}"
export GOROOT="/usr/local/go"
export CGO_ENABLED=0
export GOTOOLCHAIN=local
export GOPROXY=off
export GOFLAGS=-mod=mod
export GOCACHE="${GOCACHE:-/tmp/gocache}"
export GOTMPDIR="${GOTMPDIR:-/tmp/gotmp}"
export GOMODCACHE="${GOMODCACHE:-/tmp/gomodcache}"
mkdir -p "${GOCACHE}" "${GOTMPDIR}" "${GOMODCACHE}" /app/bin
cd /app
go build -o /app/bin/passenger-rebooking-engine ./cmd/passenger-rebooking-engine
