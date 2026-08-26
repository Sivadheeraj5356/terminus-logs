#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/main.go" /app/auth/cmd/tokensvc/main.go
cp "$SCRIPT_DIR/export.go" /app/auth/internal/audit/export.go
cp "$SCRIPT_DIR/lifecycle.go" /app/auth/internal/validator/lifecycle.go
cp "$SCRIPT_DIR/validator.go" /app/auth/internal/validator/validator.go
/app/auth/bin/build.sh
