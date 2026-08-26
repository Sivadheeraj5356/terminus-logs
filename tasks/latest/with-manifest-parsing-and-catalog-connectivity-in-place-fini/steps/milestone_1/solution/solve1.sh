#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/files/parser.ex" /app/lib/helix_pipeline/manifest/parser.ex
cp "$SCRIPT_DIR/files/client.ex" /app/lib/helix_pipeline/catalog/client.ex

bash /app/scripts/start_mysql.sh

cd /app
mix compile
mix helix.parse
