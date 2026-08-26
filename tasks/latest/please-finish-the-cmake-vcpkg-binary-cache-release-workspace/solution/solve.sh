#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/src/releasekit-cli-main.rs" /app/crates/releasekit-cli/src/main.rs
cp "$SCRIPT_DIR/src/releasekit-core-lib.rs" /app/crates/releasekit-core/src/lib.rs
cp "$SCRIPT_DIR/src/release.sh" /app/scripts/release.sh
chmod 0755 /app/scripts/release.sh

bash /app/scripts/release.sh
