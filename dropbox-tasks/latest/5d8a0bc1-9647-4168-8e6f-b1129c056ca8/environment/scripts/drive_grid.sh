#!/bin/bash
set -euo pipefail
ROOT="/app/environment"
OUT="/app/output/invariant_proof_log.json"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --full-matrix) shift ;;
    *) shift ;;
  esac
done
if [[ ! -x "${ROOT}/bin/og_check" ]]; then
  bash "${ROOT}/scripts/build_all.sh"
fi
exec "${ROOT}/bin/og_check" --full-matrix --out "${OUT}"
