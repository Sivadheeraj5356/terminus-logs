#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/keys.go" /app/auth/internal/jwk/keys.go
/app/auth/bin/build.sh
