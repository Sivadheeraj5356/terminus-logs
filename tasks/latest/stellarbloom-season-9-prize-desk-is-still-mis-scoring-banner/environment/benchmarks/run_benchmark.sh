#!/bin/bash
set -euo pipefail
export PATH="/usr/local/go/bin:/go/bin:${PATH:-}"
cd /app
/app/scripts/run_audit.sh
test -s /app/output/report.json
