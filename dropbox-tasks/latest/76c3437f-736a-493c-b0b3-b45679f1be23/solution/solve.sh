#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read the public field contract before replacing the starter dispatcher.
# Inspect the server and game engine so the policy stays within the published API.
sed -n '1,260p' "$APP_DIR/safari_runtime.md" >/dev/null
sed -n '1,260p' "$APP_DIR/src/server.mjs" >/dev/null
sed -n '1,320p' "$APP_DIR/src/game.mjs" >/dev/null
find "$APP_DIR/src" -maxdepth 2 -type f -name '*.mjs' -print >/dev/null
cp "$SCRIPT_DIR/safari_dispatch.mjs" "$APP_DIR/safari_dispatch.mjs"
