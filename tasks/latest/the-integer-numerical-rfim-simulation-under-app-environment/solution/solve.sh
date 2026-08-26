#!/usr/bin/env bash
set -euo pipefail

cd /solution
if patch --dry-run -d /app/environment -p1 < oracle.patch >/dev/null 2>&1; then
  patch -d /app/environment -p1 < oracle.patch
elif patch --dry-run -R -d /app/environment -p1 < oracle.patch >/dev/null 2>&1; then
  :
else
  echo "rfimhyst oracle patch does not match the source tree" >&2
  exit 1
fi
cd /app/environment
gofmt -w dyn/sweep.go internal/input/load.go session/run.go
go build ./cmd/fieldloop
