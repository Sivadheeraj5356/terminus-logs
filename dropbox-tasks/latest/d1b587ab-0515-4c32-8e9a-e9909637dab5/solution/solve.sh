#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/phaseglass_veil_oracle.go" /app/cmd/phaseglass-duet/main.go
cd /app
gofmt -w /app/cmd/phaseglass-duet/main.go
/usr/local/go/bin/go build -o /app/phaseglass-duet /app/cmd/phaseglass-duet
/app/phaseglass-duet --board /app/boards/public.json --output /app/out/phaseglass_policy.json
