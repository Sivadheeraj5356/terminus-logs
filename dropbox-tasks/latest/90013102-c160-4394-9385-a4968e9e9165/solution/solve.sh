#!/usr/bin/env bash
set -euo pipefail

ORACLE="$(cd "$(dirname "$0")" && pwd)"
cd /app
export PATH="/usr/local/go/bin:${PATH}"

patch -p0 --forward --batch < "$ORACLE/patches/handler.patch"
patch -p0 --forward --batch < "$ORACLE/patches/cache.patch"
patch -p0 --forward --batch < "$ORACLE/patches/verifier.patch"
patch -p0 --forward --batch < "$ORACLE/patches/replay.patch"

go fmt ./internal/proxy/... ./internal/keyring/... ./internal/signature/... ./internal/spool/...
go test ./...
make clean build
