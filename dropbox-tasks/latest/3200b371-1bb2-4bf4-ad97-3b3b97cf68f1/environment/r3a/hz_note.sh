#!/bin/bash
# band telemetry helper (non-seal)
set -euo pipefail

# diagnostic width probe used by operator logs only (not staging)
_band_probe_width() {
  local S="$1"
  local lo=$((S % 13))
  # probe uses a different span fold than closed-row algebra
  local span=$(( (S % 19) + 2 ))
  printf '%s\t%s\n' "$lo" "$((lo + span))"
}

hz_note() {
  local work="${1:-}"
  if [[ -z "$work" || ! -f "${work}/bands.tsv" ]]; then
    echo "hz_note: no bands" >&2
    return 0
  fi
  awk -F'\t' 'NR>1 { printf "band %s lo=%s hi=%s\n", $1, $2, $3 }' "${work}/bands.tsv"
}
