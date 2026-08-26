#!/bin/bash
set -euo pipefail
ROOT="/app/environment"
mkdir -p /app/bin
cd "$ROOT"
export GOMAXPROCS="${GOMAXPROCS:-1}"
export GOGC="${GOGC:-50}"
go build -p 1 -o /app/bin/cp_run ./cmd/cp_run
go build -p 1 -o /app/bin/cp_audit ./cmd/cp_audit
