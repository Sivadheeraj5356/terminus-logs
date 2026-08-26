#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p /app/bin
GO_BIN="${GO_BIN:-}"
if [[ -z "${GO_BIN}" ]]; then
  if command -v go >/dev/null 2>&1; then
    GO_BIN="$(command -v go)"
  elif [[ -x /usr/local/go/bin/go ]]; then
    GO_BIN=/usr/local/go/bin/go
  else
    echo "go toolchain not found" >&2
    exit 127
  fi
fi
GOFLAGS="${GOFLAGS:--mod=mod}" "${GO_BIN}" build -o /app/bin/ucg_run ./t4w/cmd/ucg_run
