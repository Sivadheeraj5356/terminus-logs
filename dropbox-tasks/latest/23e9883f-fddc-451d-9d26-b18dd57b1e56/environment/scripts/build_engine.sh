#!/bin/bash
set -euo pipefail
ROOT="${1:-/app}"
mkdir -p "$ROOT/bin"
cd "$ROOT"
go build -o "$ROOT/bin/mode_seal" ./cmd/mode_seal
