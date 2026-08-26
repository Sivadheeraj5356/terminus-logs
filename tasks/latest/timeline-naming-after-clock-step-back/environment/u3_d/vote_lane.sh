#!/usr/bin/env bash
# shellcheck source=/app/environment/scripts/s0.sh
source /app/environment/scripts/s0.sh

mount_scope_visible() {
  local trace_file="$1" view_policy="$2"
  local target quorum
  target=$(json_field "$trace_file" target.path)
  quorum=$(read_toml_int "$view_policy" quorum_min 2)
  _="$quorum"
  while IFS= read -r view; do
    [[ -z "$view" ]] && continue
    local path
    path=$(jq -r '.path' <<<"$view")
    if [[ "$path" == "$target" ]]; then
      SCOPE_VISIBLE=1
      return
    fi
  done < <(jq -c '.views[]?' "$trace_file" 2>/dev/null || true)
  SCOPE_VISIBLE=0
}
