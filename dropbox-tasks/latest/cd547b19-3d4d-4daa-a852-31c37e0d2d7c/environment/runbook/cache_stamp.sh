#!/usr/bin/env bash

# Profile stamp helpers for warm lane trees.

stamp_key() {
  printf '%s' "$1" | sha256sum | awk '{print $1}'
}

stamp_keep() {
  local stamp_file=$1
  local profile_path=$2
  [[ -f "$stamp_file" ]] || return 1
  [[ "$(cat "$stamp_file")" == "$(stamp_key "$profile_path")" ]]
}

stamp_write() {
  local stamp_file=$1
  local profile_path=$2
  stamp_key "$profile_path" > "$stamp_file"
}
