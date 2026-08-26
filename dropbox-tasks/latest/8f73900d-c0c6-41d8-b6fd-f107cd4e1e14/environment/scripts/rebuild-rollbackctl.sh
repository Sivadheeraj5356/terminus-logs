#!/usr/bin/env bash
set -euo pipefail
PATH="/usr/local/go/bin:/usr/local/bin:/usr/bin:${PATH}"
cd /app
if command -v gofmt >/dev/null 2>&1; then
  gofmt -w ./cmd ./internal 2>/dev/null || true
fi
go build -o /app/bin/rollbackctl ./cmd/rollbackctl
