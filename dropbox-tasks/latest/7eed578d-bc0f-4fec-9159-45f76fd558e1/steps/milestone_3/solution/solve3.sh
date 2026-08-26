#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/build_worker.sh"
/app/risk_worker verify-ledger --batch BATCH-001 --ledger /app/data/ledger/batch_001.csv
/app/risk_worker populate-features --batch BATCH-001
/app/risk_worker run-scoring --job JOB-20250620-001
