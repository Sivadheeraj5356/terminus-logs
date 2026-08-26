#!/bin/bash
set -euo pipefail

ROOT="/app/environment"
BIN="${ROOT}/bin"
SIM="${BIN}/h7_sim"
H7D="${BIN}/h7d"
MAPS="${ROOT}/fixtures/maps"
OUT="/app/output/ladder_replay_report.json"

mkdir -p /app/output

"${H7D}" -maps "${MAPS}" -out "${OUT}" -sim "${SIM}"
