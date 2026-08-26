#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/files/queries.ex" /app/lib/helix_pipeline/catalog/queries.ex
cp "$SCRIPT_DIR/files/builder.ex" /app/lib/helix_pipeline/lock/builder.ex

bash /app/scripts/start_mysql.sh

cd /app
mix compile
mix helix.lock
