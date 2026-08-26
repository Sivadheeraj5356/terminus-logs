#!/bin/bash
# Builds the labyrinth-oracle binary from /app into /app/bin.
set -euo pipefail

cd /app
mkdir -p /app/bin /app/hint-scratch
if [ ! -d vendor ]; then
  go mod vendor
fi
go build -mod=vendor -o /app/bin/labyrinth-oracle ./cmd/labyrinth-oracle
