#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/usr/local/go/bin:${PATH}"
export HOME="${HOME:-/home/model}"
export GOCACHE="${GOCACHE:-$HOME/.cache/go-build}"
export GOMODCACHE="${GOMODCACHE:-$HOME/go/pkg/mod}"
mkdir -p "$GOCACHE" "$GOMODCACHE"
cd "$ROOT"
mkdir -p "$ROOT/bin" "$ROOT/output" "$ROOT/work" "$ROOT/legacy"
go build -o "$ROOT/bin/desk" ./desk_bin
go build -o "$ROOT/bin/legacy" ./legacy_bin
