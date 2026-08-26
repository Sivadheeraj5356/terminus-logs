#!/bin/bash
set -euo pipefail
cd /app/src
mkdir -p /app/bin
rm -f /app/bin/amberglass
if command -v go >/dev/null 2>&1; then
  GO_BIN="$(command -v go)"
elif [ -x /usr/local/go/bin/go ]; then
  GO_BIN=/usr/local/go/bin/go
else
  exit 1
fi
CGO_ENABLED=0 "$GO_BIN" build -mod=readonly -trimpath -o /app/bin/amberglass .
