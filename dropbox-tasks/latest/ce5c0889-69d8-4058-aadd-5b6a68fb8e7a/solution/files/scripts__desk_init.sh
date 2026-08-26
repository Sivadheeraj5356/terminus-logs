#!/bin/bash
set -euo pipefail
mkdir -p /app/run /app/output
rm -f /app/run/move_rules.sqlite
sqlite3 /app/run/move_rules.sqlite < /app/data/seed_bootstrap.sql
echo "desk store ready"
