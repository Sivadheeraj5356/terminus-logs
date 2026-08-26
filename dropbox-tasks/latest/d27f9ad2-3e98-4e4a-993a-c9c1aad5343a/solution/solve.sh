#!/bin/bash
set -euo pipefail

cd /app
patch -p1 < /solution/fix.patch
gofmt -w internal/engine/engine.go
go build -o latmon ./cmd/latmon
