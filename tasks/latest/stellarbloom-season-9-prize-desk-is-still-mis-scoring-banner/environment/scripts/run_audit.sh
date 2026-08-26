#!/bin/bash
set -euo pipefail
export PATH="/usr/local/go/bin:/go/bin:${PATH:-}"
cd /app
go build -o /app/bin/gachaudit ./cmd/gachaudit
rm -f /app/output/pity_ledger.json
/app/bin/gachaudit \
  --input /app/data/sessions.json \
  --config /app/config/gacha.json \
  --override /app/config/live_overrides.toml \
  --ledger /app/output/pity_ledger.json \
  --output /app/output/report.json
