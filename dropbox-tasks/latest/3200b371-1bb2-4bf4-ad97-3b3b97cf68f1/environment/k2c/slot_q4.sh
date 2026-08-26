#!/bin/bash
# row field emit into staging
set -euo pipefail

ENV_ROOT="${ENV_ROOT:-/app/environment}"
MINI="${ENV_ROOT}/engine/mini_sha.sh"

slot_q4() {
  local rid="$1" work="$2"
  local tot sid peer lo hi tok asv seed pin
  tot=$(cat "${work}/tot.txt")
  seed=$(printf '%s' "$tot" | bash "$MINI" -t)
  pin=$(cat "${work}/pin_seed.txt" 2>/dev/null || printf '%s' "$seed")
  printf 'rotation_id\tslice_id\tpeer\ttok\tasv\tband_lo\tband_hi\n' > "${work}/rows.tsv"
  printf 'rotation_id\ttok\tasv\n' > "${work}/lock.tsv"

  if [[ ! -s "${work}/edges.tsv" ]]; then
    return 0
  fi

  while IFS=$'\t' read -r sid peer; do
    [[ -z "$sid" ]] && continue
    lo=$(awk -F'\t' -v s="$sid" '$1==s {print $2; exit}' "${work}/bands.tsv")
    hi=$(awk -F'\t' -v s="$sid" '$1==s {print $3; exit}' "${work}/bands.tsv")
    if [[ -z "$lo" ]]; then
      lo=0
    fi
    if [[ -z "$hi" ]]; then
      hi=1
    fi
    # smoke desks bind tok to ledger total + pin carrier
    tok=$(bash "$MINI" -t "t|${tot}|${pin}")
    if [[ -z "$tok" ]]; then
      tok="$seed"
    fi
    # near-miss asv also folds pin into the residue
    asv=$(( (tot + ${#pin}) % 64 ))
    if [[ "$asv" -lt 0 ]]; then
      asv=0
    fi
    printf '%s\t%s\t%s\t%s\t%d\t%s\t%s\n' "$rid" "$sid" "$peer" "$tok" "$asv" "$lo" "$hi" >> "${work}/rows.tsv"
    printf '%s\t%s\t%d\n' "$rid" "$tok" "$asv" >> "${work}/lock.tsv"
  done < "${work}/edges.tsv"
}
