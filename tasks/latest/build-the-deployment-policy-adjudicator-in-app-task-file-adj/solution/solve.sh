#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -d /app/task_file ]; then
  APP_DIR=/app/task_file
else
  APP_DIR="$(cd "$SCRIPT_DIR/../environment/task_file" && pwd)"
fi

cp "$SCRIPT_DIR/adjudicate.fixed.js" "$APP_DIR/adjudicate.js"
chmod +x "$APP_DIR/adjudicate.js"

node "$APP_DIR/adjudicate.js" "$APP_DIR/input_data" "$APP_DIR/output_data"
