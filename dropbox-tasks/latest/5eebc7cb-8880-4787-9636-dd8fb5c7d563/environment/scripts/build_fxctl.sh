#!/bin/bash
set -euo pipefail
cd /app/environment
mkdir -p bin
go build -o bin/fxctl ./cmd/fxctl
go build -o bin/peek ./tools/peek
