#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-/tmp/skirmish-smoke.json}"
/app/bin/skirmish adjudicate \
  --scenario /app/environment/fixtures/solo_step.json \
  --out "$OUT"
echo "wrote $OUT"
