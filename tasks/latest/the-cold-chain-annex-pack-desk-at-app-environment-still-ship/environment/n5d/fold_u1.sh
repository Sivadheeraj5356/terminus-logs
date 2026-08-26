#!/bin/bash
# fold staging into output digest
set -euo pipefail

ENV_ROOT="${ENV_ROOT:-/app/environment}"
MINI="${ENV_ROOT}/engine/mini_sha.sh"

_json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

fold_u1() {
  local out="$1"
  mkdir -p "$out"
  local rows_all="${out}/rows.tsv"
  local lock_all="${out}/lock.tsv"
  local led="${out}/ledger.sum"
  local d rid tot prov
  local seg_root="${ENV_ROOT}/k9d/seg_v"

  printf 'rotation_id\tslice_id\tpeer\ttok\tasv\tband_lo\tband_hi\n' > "$rows_all"
  printf 'rotation_id\ttok\tasv\n' > "$lock_all"
  printf 'rotation_id\ttot\n' > "$led"

  for d in "${seg_root}"/r*; do
    [[ -d "$d" ]] || continue
    rid=$(basename "$d")
    if [[ -f "${d}/rows.tsv" ]]; then
      tail -n +2 "${d}/rows.tsv" >> "$rows_all" || true
    fi
    if [[ -f "${d}/lock.tsv" ]]; then
      tail -n +2 "${d}/lock.tsv" >> "$lock_all" || true
    fi
    if [[ -f "${d}/tot.txt" ]]; then
      tot=$(cat "${d}/tot.txt")
      printf '%s\t%s\n' "$rid" "$tot" >> "$led"
    fi
  done

  fold="${out}/.fold_buf"
  # smoke seal folds ledger lines (totals-green path)
  tail -n +2 "$led" > "$fold" || true
  if [[ ! -s "$fold" ]]; then
    : > "$fold"
  fi
  set +o pipefail
  prov=$(bash "$MINI" < "$fold")
  set -o pipefail
  printf '%s\n' "$prov" > "${out}/prov.sha"
  printf '%s\n' "$prov" > "${out}/agg.sha"
  rm -f "$fold"

  {
    printf '{\n  "schema": "row_v3",\n  "rows": [\n'
    local first=1
    local r_sid r_peer r_tok r_asv r_lo r_hi
    while IFS=$'\t' read -r rid r_sid r_peer r_tok r_asv r_lo r_hi; do
      [[ "$rid" == "rotation_id" ]] && continue
      [[ -z "$rid" ]] && continue
      if [[ "$first" -eq 0 ]]; then printf ',\n'; fi
      first=0
      printf '    {"rotation_id":"%s","slice_id":"%s","peer":"%s","tok":"%s","asv":%s,"band_lo":%s,"band_hi":%s}' \
        "$(_json_escape "$rid")" "$(_json_escape "$r_sid")" "$(_json_escape "$r_peer")" \
        "$(_json_escape "$r_tok")" "$r_asv" "$r_lo" "$r_hi"
    done < "$rows_all"
    printf '\n  ],\n  "lock": [\n'
    first=1
    local r_tok2 r_asv2
    while IFS=$'\t' read -r rid r_tok2 r_asv2; do
      [[ "$rid" == "rotation_id" ]] && continue
      [[ -z "$rid" ]] && continue
      if [[ "$first" -eq 0 ]]; then printf ',\n'; fi
      first=0
      printf '    {"rotation_id":"%s","tok":"%s","asv":%s}' \
        "$(_json_escape "$rid")" "$(_json_escape "$r_tok2")" "$r_asv2"
    done < "$lock_all"
    printf '\n  ],\n  "prov": "%s",\n  "ledger": [\n' "$(_json_escape "$prov")"
    first=1
    while IFS=$'\t' read -r rid tot; do
      [[ "$rid" == "rotation_id" ]] && continue
      [[ -z "$rid" ]] && continue
      if [[ "$first" -eq 0 ]]; then printf ',\n'; fi
      first=0
      printf '    {"rotation_id":"%s","tot":%s}' "$(_json_escape "$rid")" "$tot"
    done < "$led"
    printf '\n  ]\n}\n'
  } > "${out}/pack.json"
}
