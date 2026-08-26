#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/main.go" /app/main.go
cd /app
/usr/local/go/bin/go build -o /app/macaroon-audit .
/app/macaroon-audit
test -f /app/output/report.json

