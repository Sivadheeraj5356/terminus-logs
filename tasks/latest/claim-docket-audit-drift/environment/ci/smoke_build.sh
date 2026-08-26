#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
go build -o /app/bin/claimdocketaudit ./cmd/claimdocketaudit
test -x /app/bin/claimdocketaudit
