#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd /app
export PATH="/usr/local/go/bin:${PATH}"
export GOPROXY=off
export GOSUMDB=off
export CGO_ENABLED=0

cp "$SCRIPT_DIR/files/resolver.go" /app/internal/graph/resolver.go
cp "$SCRIPT_DIR/files/compare.go" /app/internal/semver/compare.go
cp "$SCRIPT_DIR/files/load.go" /app/internal/config/load.go
cp "$SCRIPT_DIR/files/handlers.go" /app/internal/api/handlers.go
cp "$SCRIPT_DIR/files/openapi.go" /app/internal/api/openapi.go
mkdir -p /app/internal/attest
cp "$SCRIPT_DIR/files/attest.go" /app/internal/attest/attest.go
cp "$SCRIPT_DIR/files/emit-fleet-build-audit.sh" /app/scripts/emit-fleet-build-audit.sh
chmod +x /app/scripts/emit-fleet-build-audit.sh /app/scripts/start-fleetd.sh

go build -o /app/bin/fleetd ./cmd/fleetd
test -x /app/bin/fleetd
