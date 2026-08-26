#!/bin/bash
# smoke-only health probe (aggregate totals)
set -euo pipefail

ENV_ROOT="${ENV_ROOT:-/app/environment}"
OUT="${OUT_ROOT:-/app/output/policy_pack}"

ready_g8() {
  if [[ ! -f "${OUT}/ledger.sum" ]]; then
    echo "ready_g8: missing ledger"
    return 1
  fi
  # compare each rotation tot against sum_tbl membership
  local ok=1
  local rid tot expect
  while IFS=$'\t' read -r rid tot; do
    [[ "$rid" == "rotation_id" ]] && continue
    [[ -z "$rid" ]] && continue
    local corpus
    corpus=$(awk -v id="$rid" '
      /^\[\[row\]\]/ { cur="" }
      /^id = / { gsub(/"/,"",$3); if ($3==id) cur=id }
      /^corpus = / { if (cur==id) { gsub(/"/,"",$3); print $3; exit } }
    ' "${ENV_ROOT}/data/rot_tbl.toml")
    expect=0
    local sid S
    IFS=',' read -r -a ids <<< "$corpus"
    for sid in "${ids[@]}"; do
      S=$(awk -F'\t' -v s="$sid" '$1==s {print $2; exit}' "${ENV_ROOT}/data/fix_stash/sum_tbl.tsv")
      expect=$((expect + S))
    done
    if [[ "$tot" -ne "$expect" ]]; then
      echo "ready_g8: mismatch $rid"
      ok=0
    fi
  done < "${OUT}/ledger.sum"
  if [[ "$ok" -eq 1 ]]; then
    echo "ready_g8: ok"
    return 0
  fi
  return 1
}
