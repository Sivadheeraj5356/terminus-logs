#!/bin/bash
set -euo pipefail

# Works as root (platform oracle) or rebooker (agent-path / local Harbor-like probe).
export HOME="${HOME:-/home/rebooker}"
export PATH="/usr/local/go/bin:/app/bin:/usr/bin:${PATH}"
export GOROOT="/usr/local/go"
export CGO_ENABLED=0
export GOTOOLCHAIN=local
export GOPROXY=off
export GOFLAGS=-mod=mod
export GOCACHE="${GOCACHE:-/tmp/gocache}"
export GOTMPDIR="${GOTMPDIR:-/tmp/gotmp}"
export GOMODCACHE="${GOMODCACHE:-/tmp/gomodcache}"

mkdir -p "${GOCACHE}" "${GOTMPDIR}" "${GOMODCACHE}" /app/state /app/output /app/bin

SOL_DIR="/solution"
if [ ! -d "${SOL_DIR}" ]; then
  SOL_DIR="/task/solution"
fi

cp "${SOL_DIR}/ingest_digest.go" /app/internal/ingest/digest.go
cp "${SOL_DIR}/stage_collapse.go" /app/internal/stage/collapse.go
cp "${SOL_DIR}/stage_allocate.go" /app/internal/stage/allocate.go
cp "${SOL_DIR}/staging_publish.go" /app/internal/staging/publish.go
cp "${SOL_DIR}/stage_run.go" /app/internal/stage/run.go
cp "${SOL_DIR}/export_publish.go" /app/internal/export/publish.go

# Ensure rebooker can continue editing after a root oracle run.
if [ "$(id -u)" -eq 0 ] && id -u rebooker >/dev/null 2>&1; then
  chown -R rebooker:rebooker /app/state /app/output /app/bin /app/internal /app/cmd 2>/dev/null || true
fi

cd /app
bash /app/scripts/build.sh
test -x /app/bin/passenger-rebooking-engine

/app/bin/passenger-rebooking-engine build

test -f /app/state/rebooking-snapshot.json
test -f /app/state/rebooking-ledger.json
test -f /app/output/rebooking-plan.json
test -f /app/output/passenger-summary.json
