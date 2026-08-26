#!/usr/bin/env bash
# Print the tables in the local database.
set -euo pipefail
sqlite3 /app/data/crosspay.db ".tables"
