#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_BIN="$(command -v go || echo /usr/local/go/bin/go)"
mkdir -p "$ROOT/bin"
cd "$ROOT"
"$GO_BIN" build -o "$ROOT/bin/lb_drive" ./cmd/lb_drive
