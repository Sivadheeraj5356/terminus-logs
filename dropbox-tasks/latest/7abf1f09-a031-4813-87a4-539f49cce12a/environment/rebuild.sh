#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/go/bin:/go/bin:${PATH}"
cd /app/carrydown_engine
go build -o /app/bin/commitment-chargeback .
