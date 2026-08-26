#!/bin/bash
set -euo pipefail
cd /app
mkdir -p /app/output
exec go run "$(dirname "$0")/verifier.go"
