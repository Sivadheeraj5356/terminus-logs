#!/bin/bash
set -euo pipefail
cd /app
CGO_ENABLED=0 go build -mod=readonly -o /app/bin/waxlane-allot ./cmd/waxlane-allot
chmod +x /app/bin/waxlane-allot
