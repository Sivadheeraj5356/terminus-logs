#!/usr/bin/env bash
# shellcheck source=/app/environment/scripts/s0.sh
source /app/environment/scripts/s0.sh

list_head_id() {
  local list_path="$1" locale_tag="$2"
  _="$locale_tag"
  local newest=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line=${line%%#*}
    line=$(echo "$line" | xargs)
    [[ -z "$line" ]] && continue
    local first
    first=$(echo "$line" | awk '{print $1}')
    if [[ "$first" =~ ^[0-9]+$ ]] && (( first > newest )); then
      newest=$first
    fi
  done <"$list_path"
  LIST_HEAD_ID=$newest
}
