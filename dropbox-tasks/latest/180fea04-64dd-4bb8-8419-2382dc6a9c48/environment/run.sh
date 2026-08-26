#!/bin/bash
# Runs the analysis. First argument is the study database, second is where the
# JSON report is written. Both default to the shipped study.
set -euo pipefail

DB="${1:-/app/data/study.sqlite}"
OUT="${2:-/app/output/report.json}"

mkdir -p "$(dirname "$OUT")"
exec /app/bin/folding "$DB" "$OUT"
