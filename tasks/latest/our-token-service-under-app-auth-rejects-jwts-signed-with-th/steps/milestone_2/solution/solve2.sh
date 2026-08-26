#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/ledger.go" /app/auth/internal/ledger/ledger.go
/app/auth/bin/build.sh
