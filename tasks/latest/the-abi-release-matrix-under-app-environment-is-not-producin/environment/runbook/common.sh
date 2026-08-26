#!/usr/bin/env bash

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

# jq predicate comparing the generated layout view with the compiled probe view.
layout_match_filter='(.generated|{lane,record_size,align,field_count,fields}) == (.compiled|{lane,record_size,align,field_count,fields})'

resolve_profile_path() {
  local matrix_dir=$1
  local raw=$2
  local env_root=$3
  if [[ "$raw" = /* ]]; then
    printf '%s\n' "$raw"
  elif [[ -f "$env_root/$raw" ]]; then
    printf '%s\n' "$env_root/$raw"
  else
    printf '%s\n' "$matrix_dir/$raw"
  fi
}
