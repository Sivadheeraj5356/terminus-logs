#!/usr/bin/env bash
set -euo pipefail

cd /app

SOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "${SOL_DIR}/archive.go" /app/vault/archive.go
cp "${SOL_DIR}/trust.go" /app/audit/trust.go

make build

test -x /app/bin/ebta
test "$(wc -c < /app/bin/ebta | tr -d ' ')" -gt 2048

mkdir -p /app/verdicts
rm -f /app/verdicts/backup_trust_report.json
/app/bin/ebta
test -s /app/verdicts/backup_trust_report.json
