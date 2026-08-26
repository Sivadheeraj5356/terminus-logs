#!/usr/bin/env bash
set -euo pipefail

cd /app
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/depotlock.go" /app/cmd/depotlock/main.go
go test ./...
