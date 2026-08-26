#!/bin/bash
set -euo pipefail

cd /app/environment
export GOCACHE=/tmp/go-cache
mkdir -p /tmp/go-cache /app/bin

GO_BIN="${GO_BIN:-/usr/local/go/bin/go}"
if [ ! -x "$GO_BIN" ]; then
  GO_BIN="$(command -v go)"
fi

"$GO_BIN" build -trimpath -o /app/bin/ctl_s8 ./cmd/ctl_s8
"$GO_BIN" build -trimpath -o /app/bin/client_t4 ./cmd/client_t4
"$GO_BIN" build -trimpath -o /app/bin/supervisord ./cmd/supervisord
