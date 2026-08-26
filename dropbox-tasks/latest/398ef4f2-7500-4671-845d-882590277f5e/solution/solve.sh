#!/usr/bin/env bash
set -euo pipefail

# Stage the reference Go source over the stub layout under /app/jetway,
# then build via the Makefile and run the binary.
SRC=/solution/source
DST=/app/jetway

mkdir -p "$DST"
rm -f "$DST"/*.go
cp "$SRC"/main.go "$DST"/main.go
cp "$SRC"/go.mod "$DST"/go.mod 2>/dev/null || true
cp "$SRC"/go.mod /app/go.mod

cd /app
make clean >/dev/null 2>&1 || true
make build
make run
