#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Poll until the model registry answers — do not rely on a fixed sleep.
python3 /app/scripts/ensure_registry.py

cp "${SCRIPT_DIR}/feature_audit.c" /app/src/feature_audit.c
make -C /app/src clean all

mkdir -p /app/output
/app/bin/feature_lineage_verdict \
  --evaluate-training-runs \
  --db /app/data/lineage.duckdb \
  --policy /app/data/governance_policy.json \
  --output /app/output
