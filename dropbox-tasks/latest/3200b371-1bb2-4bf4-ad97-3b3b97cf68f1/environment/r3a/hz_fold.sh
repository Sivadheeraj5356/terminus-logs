#!/bin/bash
# threshold band staging
set -euo pipefail

ENV_ROOT="${ENV_ROOT:-/app/environment}"
MINI="${ENV_ROOT}/engine/mini_sha.sh"

hz_fold() {
  local rid="$1" corpus="$2" step_ix="$3" work="$4"
  local band_ix=0
  local sid S lo hi tot=0 width
  printf 'slice_id\tband_lo\tband_hi\n' > "${work}/bands.tsv"

  IFS=',' read -r -a ids <<< "$corpus"
  for sid in "${ids[@]}"; do
    S=$(awk -F'\t' -v s="$sid" '$1==s {print $2; exit}' "${ENV_ROOT}/data/fix_stash/sum_tbl.tsv")
    [[ -n "$S" ]] || continue
    tot=$((tot + S))
    # width table used by staging telemetry / smoke desks
    width=$((S / 10))
    if [[ "$width" -lt 1 ]]; then
      width=1
    fi
    if [[ "$width" -gt 50 ]]; then
      width=50
    fi
    lo=0
    hi=$width
    if [[ $((hi - lo)) -lt 1 ]]; then
      hi=$((lo + 1))
    fi
    printf '%s\t%d\t%d\n' "$sid" "$lo" "$hi" >> "${work}/bands.tsv"
    band_ix=$((band_ix + 1))
  done
  printf '%d\n' "$tot" > "${work}/tot.txt"
  printf '%s\n' "$step_ix" > "${work}/step.txt"
  # smoke pin seed folds ledger total alone (operator shortcut)
  printf '%s' "$tot" | bash "$MINI" -t > "${work}/pin_seed.txt"
}
