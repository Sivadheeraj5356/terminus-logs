#!/bin/bash
set -euo pipefail
mkdir -p /app/run /app/output
sqlite3 /app/run/move_rules.sqlite < /dev/null 2>/dev/null || true
rm -f /app/run/move_rules.sqlite
touch /app/run/move_rules.sqlite
echo "desk store ready"
