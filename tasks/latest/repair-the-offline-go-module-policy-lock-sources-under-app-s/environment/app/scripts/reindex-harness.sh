#!/usr/bin/env bash
set -euo pipefail

MIRROR="${1:-/app/var/module-mirror}"
DB="${2:-/app/var/policy-index/policy.db}"
BIN="/app/bin/modpolicylock"

rm -f "$DB"
"$BIN" reindex --mirror "$MIRROR" --db "$DB"
echo "reindex complete: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM pins;') pins"
