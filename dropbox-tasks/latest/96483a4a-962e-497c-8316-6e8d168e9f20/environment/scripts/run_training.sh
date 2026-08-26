#!/bin/bash
set -euo pipefail

ROOT="/app/environment"
BIN="${ROOT}/bin"
SIM="${BIN}/h7_sim"
TRAINING="${ROOT}/fixtures/training"

mkdir -p /app/output

for sample in ridge_wrap moss_trail; do
  "${SIM}" "${TRAINING}/${sample}.json" >/dev/null
done
