#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp -R "${SCRIPT_DIR}/cmd" /app/
cp -R "${SCRIPT_DIR}/internal" /app/
cp "${SCRIPT_DIR}/go.mod" /app/go.mod
mkdir -p /app/output

cd /app
go run ./cmd/residual
