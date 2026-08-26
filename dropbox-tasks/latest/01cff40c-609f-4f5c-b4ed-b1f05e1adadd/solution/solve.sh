#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/go/bin:/app/bin:${PATH}"
export CGO_ENABLED=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "${SCRIPT_DIR}/fixed/parse/parse.go" /app/internal/parse/parse.go
cp "${SCRIPT_DIR}/fixed/ingest/ingest.go" /app/internal/ingest/ingest.go
cp "${SCRIPT_DIR}/fixed/compliance/engine.go" /app/internal/compliance/engine.go
cp "${SCRIPT_DIR}/fixed/export/export.go" /app/internal/export/export.go

/app/scripts/build.sh

mkdir -p /app/data /app/output
DB=/tmp/oracle-fert.db
rm -f "$DB"
/app/bin/fert-ingest --db "$DB" --events /app/fixtures/public/sample_events.jsonl
/app/bin/fert-export --db "$DB" --out /tmp/oracle-export.json
