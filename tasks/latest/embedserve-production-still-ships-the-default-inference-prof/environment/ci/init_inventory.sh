#!/usr/bin/env bash
set -euo pipefail

ROOT="/app/environment"
DB="/app/data/embedserve_inventory.db"

sqlite3 "$DB" < "$ROOT/sql/schema.sql"
sqlite3 "$DB" < "$ROOT/sql/seed_inventory.sql"
