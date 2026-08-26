#!/bin/bash
# multi-phase orchestration for pp_run
set -euo pipefail

ENV_ROOT="${ENV_ROOT:-/app/environment}"
seg_root="${ENV_ROOT}/k9d/seg_v"
OUT="${OUT_ROOT:-/app/output/policy_pack}"

# shellcheck source=/dev/null
source "${ENV_ROOT}/r3a/hz_fold.sh"
# shellcheck source=/dev/null
source "${ENV_ROOT}/k2c/slot_q4.sh"
# shellcheck source=/dev/null
source "${ENV_ROOT}/n5d/fold_u1.sh"
# shellcheck source=/dev/null
source "${ENV_ROOT}/n5d/ready_g8.sh"
# shellcheck source=/dev/null
source "${ENV_ROOT}/r3a/hz_note.sh"
# shellcheck source=/dev/null
source "${ENV_ROOT}/k2c/slot_note.sh"

parse_rot_tbl() {
  local tbl="${ENV_ROOT}/data/rot_tbl.toml"
  awk '
    /^\[\[row\]\]/ { if (id != "") printf "%s\t%s\t%s\t%s\n", id, corpus, lane, step; id=""; corpus=""; lane=""; step="0"; next }
    /^id = / { gsub(/"/, "", $3); id=$3; next }
    /^corpus = / { gsub(/"/, "", $3); corpus=$3; next }
    /^lane = / { gsub(/"/, "", $3); lane=$3; next }
    /^step = / { step=$3; next }
    END { if (id != "") printf "%s\t%s\t%s\t%s\n", id, corpus, lane, step }
  ' "$tbl"
}

load_sums() {
  awk -F'\t' 'NR>1 { print $1 "\t" $2 }' "${ENV_ROOT}/data/fix_stash/sum_tbl.tsv"
}

run_one_rotation() {
  local rid="$1" corpus="$2" lane="$3" step="$4"
  local work="${seg_root}/${rid}"
  mkdir -p "$work"
  rm -f "${work}/bands.tsv" "${work}/edges.tsv" "${work}/rows.tsv" "${work}/lock.tsv" "${work}/tot.txt" "${work}/pin_seed.txt" "${work}/step.txt"

  # phase 1: band + pin carrier
  hz_fold "$rid" "$corpus" "$step" "$work"

  # phase 2: edges via awk
  local active_csv="$corpus"
  awk -v active="$active_csv" -v out="${work}/edges.tsv" -f "${ENV_ROOT}/q7b/knit_z7.awk" \
    "${ENV_ROOT}/data/corpus/"*_blob.dbc

  # phase 3: rows (consumes bands + pin_seed + edges)
  slot_q4 "$rid" "$work"

  # phase 4: stage done; seal gathers later
  :
}

orch_rebuild() {
  local only_id="${1:-}"
  mkdir -p "$seg_root" "$OUT"
  rm -rf "${OUT:?}/"*
  mkdir -p "$OUT"

  local rid corpus lane step
  while IFS=$'\t' read -r rid corpus lane step; do
    [[ -z "$rid" ]] && continue
    if [[ -n "$only_id" && "$rid" != "$only_id" ]]; then
      continue
    fi
    run_one_rotation "$rid" "$corpus" "$lane" "$step"
  done < <(parse_rot_tbl)

  fold_u1 "$OUT"
}

orch_health() {
  ready_g8
}
