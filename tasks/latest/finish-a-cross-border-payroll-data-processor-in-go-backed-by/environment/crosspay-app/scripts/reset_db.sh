#!/usr/bin/env bash
# Remove the local database so the next run starts from an empty state.
set -euo pipefail
rm -f /app/data/crosspay.db
echo "database reset"
