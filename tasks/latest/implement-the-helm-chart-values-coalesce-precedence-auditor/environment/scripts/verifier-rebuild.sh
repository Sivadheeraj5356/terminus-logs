#!/bin/bash
set -euo pipefail
export GOROOT="${GOROOT:-/usr/local/go}"
export PATH="${GOROOT}/bin:${PATH}"
cd /app
go build -mod=readonly -o /app/bin/helmvals ./cmd/helmvals
