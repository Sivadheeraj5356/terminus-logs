#!/usr/bin/env bash
set -euo pipefail
cd /app

ORACLE_ROOT="$(cd "$(dirname "$0")" && pwd)"

cp -f "$ORACLE_ROOT/fixed/ampstore/vector/state.go" /app/ampstore/vector/state.go
cp -f "$ORACLE_ROOT/fixed/gatekron/ops/gates.go" /app/gatekron/ops/gates.go
cp -f "$ORACLE_ROOT/fixed/numpolicy/tol/resolve.go" /app/numpolicy/tol/resolve.go
cp -f "$ORACLE_ROOT/fixed/circexec/engine/run.go" /app/circexec/engine/run.go
cp -f "$ORACLE_ROOT/fixed/qwavectl/cmd/qwavectl/main.go" /app/qwavectl/cmd/qwavectl/main.go

make clean || true
make build
make run
