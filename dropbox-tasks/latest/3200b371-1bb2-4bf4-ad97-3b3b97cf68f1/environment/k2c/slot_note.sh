#!/bin/bash
# human-readable summary formatter (support tooling)
set -euo pipefail

slot_note() {
  local work="${1:-}"
  if [[ -z "$work" || ! -f "${work}/rows.tsv" ]]; then
    echo "slot_note: empty"
    return 0
  fi
  awk -F'\t' 'NR>1 { c++ } END { printf "slot_note rows=%d\n", c+0 }' "${work}/rows.tsv"
}
