#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p /app/bin
cp "$SCRIPT_DIR/oracle/flood_route.rb" /app/bin/channel-route
chmod +x /app/bin/channel-route
/app/bin/channel-route /app/data/survey.bin
