#!/usr/bin/env bash
set -euo pipefail
ARM="cedar"
BAND="dawn"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --arm) ARM="$2"; shift 2 ;;
    --band) BAND="$2"; shift 2 ;;
    *) shift ;;
  esac
done
/app/environment/bin/grti_matrix_k9 --arm "$ARM" --band "$BAND" --witness-out /app/output/stage/grid_${ARM}_${BAND}.json
