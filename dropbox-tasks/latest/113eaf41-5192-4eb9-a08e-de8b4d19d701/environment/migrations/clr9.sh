#!/usr/bin/env bash
set -euo pipefail
ROOT="/app/environment"
if [[ "${1:-}" == "--recover" ]]; then
  rm -rf /app/output/stage /app/output/rule_witness.json
  mkdir -p /app/output/stage
  echo '{"recovered":true}' > /app/output/stage/recover_stamp.json
  if [[ -f "${ROOT}/k5_n6/src/repeat_store.rs" ]]; then
    : # journal reset happens on next bake
  fi
  exit 0
fi
rm -rf /app/output/stage /app/output/rule_witness.json
rm -f /app/output/logs/*.txt 2>/dev/null || true
mkdir -p /app/output/stage
echo "wiped" > /app/output/stage/wipe_stamp.json
