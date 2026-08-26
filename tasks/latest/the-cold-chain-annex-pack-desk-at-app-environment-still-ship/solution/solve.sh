#!/bin/bash
set -euo pipefail

cat > "/app/environment/r3a/hz_fold.sh" <<'EOF'
#!/bin/bash
# threshold band staging
set -euo pipefail

ENV_ROOT="${ENV_ROOT:-/app/environment}"

hz_fold() {
  local rid="$1" corpus="$2" step_ix="$3" work="$4"
  local band_ix=0
  local sid S lo hi tot=0 span pin
  local seed_buf="${work}/.seed_buf"
  printf 'slice_id\tband_lo\tband_hi\n' > "${work}/bands.tsv"
  : > "$seed_buf"

  read -r -a ids <<< "$(printf '%s' "$corpus" | tr ',' ' ')"
  local sorted sid_sorted
  sorted=$(printf '%s\n' "${ids[@]}" | LC_ALL=C sort)
  while IFS= read -r sid_sorted; do
    [[ -z "$sid_sorted" ]] && continue
    S=$(awk -F'\t' -v s="$sid_sorted" '$1==s {print $2; exit}' "${ENV_ROOT}/data/fix_stash/sum_tbl.tsv")
    [[ -n "$S" ]] || continue
    tot=$((tot + S))
    lo=$(( (S + step_ix) % 13 ))
    span=$(( (S % 17) + 3 ))
    hi=$((lo + span))
    printf '%s\t%d\t%d\n' "$sid_sorted" "$lo" "$hi" >> "${work}/bands.tsv"
    printf '%s|%d\n' "$sid_sorted" "$lo" >> "$seed_buf"
    band_ix=$((band_ix + 1))
  done <<< "$sorted"

  printf '%d\n' "$tot" > "${work}/tot.txt"
  printf '%s\n' "$step_ix" > "${work}/step.txt"
  printf '%d\n' "$band_ix" > "${work}/band_n.txt"
  set +o pipefail
  pin=$(sha256sum < "$seed_buf" | awk '{print substr($1,1,8)}')
  set -o pipefail
  printf '%s\n' "$pin" > "${work}/pin_seed.txt"
  rm -f "$seed_buf"
}
EOF

cat > "/app/environment/q7b/knit_z7.awk" <<'EOF'
# mux edge resolve (awk)
# invoked: awk -v active=csv -v out=path -f knit_z7.awk corpus/*.dbc

function knit_z7(src, dst, mux,    a, n, i, ok) {
  n = split(active, a, ",")
  ok = 0
  for (i = 1; i <= n; i++) if (a[i] == dst) ok = 1
  if (!ok) return
  print src "\t" dst >> out
}

function in_active(id,    a, n, i) {
  n = split(active, a, ",")
  for (i = 1; i <= n; i++) if (a[i] == id) return 1
  return 0
}

BEGIN {
  cur = ""
  past_preamble = 0
  printf "" > out
  close(out)
}

FNR == 1 {
  cur = ""
  past_preamble = 0
}

/^;/ {
  past_preamble = 1
  next
}

/^BO_ / {
  cur = $NF
  next
}

/^PEER / {
  if (past_preamble) next
  if (cur == "") next
  if (!in_active(cur)) next
  if (!in_active($2)) next
  knit_z7(cur, $2, "x")
  next
}

END {
  if (out != "") {
    close(out)
  }
}
EOF

cat > "/app/environment/k2c/slot_q4.sh" <<'EOF'
#!/bin/bash
# row field emit into staging
set -euo pipefail

ENV_ROOT="${ENV_ROOT:-/app/environment}"
MINI="${ENV_ROOT}/engine/mini_sha.sh"

_byte_sum() {
  printf '%s' "$1" | od -An -tu1 | awk '{for (i = 1; i <= NF; i++) s += $i} END {print s + 0}'
}

slot_q4() {
  local rid="$1" work="$2"
  local sid peer lo hi tok asv bsum pin
  pin=$(tr -d '\n' < "${work}/pin_seed.txt")
  printf 'rotation_id\tslice_id\tpeer\ttok\tasv\tband_lo\tband_hi\n' > "${work}/rows.tsv"
  printf 'rotation_id\ttok\tasv\n' > "${work}/lock.tsv"

  if [[ ! -s "${work}/edges.tsv" ]]; then
    return 0
  fi

  while read -r sid peer; do
    [[ -z "$sid" ]] && continue
    lo=$(awk -F'\t' -v s="$sid" '$1==s {print $2; exit}' "${work}/bands.tsv")
    hi=$(awk -F'\t' -v s="$sid" '$1==s {print $3; exit}' "${work}/bands.tsv")
    if [[ -z "$lo" ]]; then
      lo=0
    fi
    if [[ -z "$hi" ]]; then
      hi=1
    fi
    tok=$(bash "$MINI" -t "t|${sid}|${peer}|${lo}|${pin}")
    if [[ -z "$tok" ]]; then
      tok="00000000"
    fi
    bsum=$(_byte_sum "$sid")
    asv=$(( (bsum + lo) % 64 ))
    if [[ "$asv" -lt 0 ]]; then
      asv=0
    fi
    if [[ "$asv" -gt 63 ]]; then
      asv=$((asv % 64))
    fi
    printf '%s\t%s\t%s\t%s\t%d\t%s\t%s\n' "$rid" "$sid" "$peer" "$tok" "$asv" "$lo" "$hi" >> "${work}/rows.tsv"
    printf '%s\t%s\t%d\n' "$rid" "$tok" "$asv" >> "${work}/lock.tsv"
  done < "${work}/edges.tsv"
}
EOF

cat > "/app/environment/n5d/fold_u1.sh" <<'EOF'
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
  tail -n +2 "$rows_all" | LC_ALL=C sort -t $'\t' -k1,1 -k2,2 -k3,3 \
    | awk -F'\t' 'NF{print $4 "|" $5}' > "$fold" || true
  if [[ ! -s "$fold" ]]; then
    : > "$fold"
  fi
  set +o pipefail
  prov=$(bash "$MINI" < "$fold")
  set -o pipefail
  printf '%s\n' "$prov" > "${out}/prov.sha"
  if [[ -f "${out}/agg.sha" ]]; then
    rm -f "${out}/agg.sha"
  fi
  rm -f "$fold"

  {
    printf '{\n  "schema": "row_v3",\n  "rows": [\n'
    local first=1
    local r_sid r_peer r_tok r_asv r_lo r_hi
    while read -r rid r_sid r_peer r_tok r_asv r_lo r_hi; do
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
    while read -r rid r_tok2 r_asv2; do
      [[ "$rid" == "rotation_id" ]] && continue
      [[ -z "$rid" ]] && continue
      if [[ "$first" -eq 0 ]]; then printf ',\n'; fi
      first=0
      printf '    {"rotation_id":"%s","tok":"%s","asv":%s}' \
        "$(_json_escape "$rid")" "$(_json_escape "$r_tok2")" "$r_asv2"
    done < "$lock_all"
    printf '\n  ],\n  "prov": "%s",\n  "ledger": [\n' "$(_json_escape "$prov")"
    first=1
    while read -r rid tot; do
      [[ "$rid" == "rotation_id" ]] && continue
      [[ -z "$rid" ]] && continue
      if [[ "$first" -eq 0 ]]; then printf ',\n'; fi
      first=0
      printf '    {"rotation_id":"%s","tot":%s}' "$(_json_escape "$rid")" "$tot"
    done < "$led"
    printf '\n  ]\n}\n'
  } > "${out}/pack.json"
}
EOF

chmod +x "/app/environment/r3a/hz_fold.sh" "/app/environment/k2c/slot_q4.sh" "/app/environment/n5d/fold_u1.sh"
/app/h7p/pp_run rebuild
