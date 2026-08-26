#!/usr/bin/env bash
# shellcheck source=/app/environment/scripts/s0.sh
source /app/environment/scripts/s0.sh

pick_label_rows() {
  local trace_file="$1"
  local best_text="" best_epoch=999999
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    local text epoch
    text=$(jq -r '.text' <<<"$row")
    epoch=$(jq -r '.epoch' <<<"$row")
    if [[ -z "$best_text" || "$text" > "$best_text" ]]; then
      best_text=$text
      best_epoch=$epoch
    elif [[ "$text" == "$best_text" && "$epoch" -lt "$best_epoch" ]]; then
      best_epoch=$epoch
    fi
  done < <(jq -c '.labels[]?' "$trace_file" 2>/dev/null || true)
  LABEL_PICK=$best_text
  LABEL_EPOCH=$best_epoch
}
