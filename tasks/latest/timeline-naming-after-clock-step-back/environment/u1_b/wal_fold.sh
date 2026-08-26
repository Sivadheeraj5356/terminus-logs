#!/usr/bin/env bash
# shellcheck source=/app/environment/scripts/s0.sh
source /app/environment/scripts/s0.sh

wal_override_label() {
  local trace_file="$1"
  local best_text="" best_epoch=0 best_fname="" cursor=0
  while IFS= read -r seg; do
    [[ -z "$seg" ]] && continue
    local fname seq text epoch
    fname=$(jq -r '.file_name' <<<"$seg")
    seq=$(jq -r '.seq' <<<"$seg")
    text=$(jq -r '.override.text // empty' <<<"$seg")
    epoch=$(jq -r '.override.epoch // 0' <<<"$seg")
    if (( seq > cursor )); then cursor=$seq; fi
    if [[ -n "$text" ]]; then
      if [[ -z "$best_fname" || "$fname" < "$best_fname" ]]; then
        best_fname=$fname
        best_text=$text
        best_epoch=$epoch
      fi
    fi
  done < <(jq -c '.wal_segments[]?' "$trace_file" 2>/dev/null || true)
  WAL_CURSOR=$cursor
  WAL_OVERRIDE_TEXT=$best_text
  WAL_OVERRIDE_EPOCH=$best_epoch
  WAL_HAS_OVERRIDE=0
  if [[ -n "$best_text" ]]; then
    WAL_HAS_OVERRIDE=1
  fi
}
