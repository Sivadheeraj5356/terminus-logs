#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/main.go" /app/src/main.go
/app/src/build.sh
