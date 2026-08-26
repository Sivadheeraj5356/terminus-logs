#!/usr/bin/env bash
set -euo pipefail
cd /app
CGO_ENABLED=0 go build -o /app/bin/lng-boiloff-reconciler ./cmd/lng-boiloff-reconciler
