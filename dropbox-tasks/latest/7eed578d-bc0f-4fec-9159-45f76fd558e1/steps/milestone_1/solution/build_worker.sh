#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_SRC="${SCRIPT_DIR}/worker"

cp -a "${WORKER_SRC}/." /app/
make -C /app clean all
/app/risk_worker verify-ledger --batch BATCH-001 --ledger /app/data/ledger/batch_001.csv
