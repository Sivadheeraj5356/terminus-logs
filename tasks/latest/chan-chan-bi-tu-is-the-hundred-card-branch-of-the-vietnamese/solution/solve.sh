#!/bin/bash
set -euo pipefail

cp /solution/internal/chandeck/trace.go /app/internal/chandeck/trace.go
cd /app
CGO_ENABLED=0 go build -o /tmp/chandeck_bin ./cmd/chandeck
echo "solve.sh: built /tmp/chandeck_bin" 1>&2
