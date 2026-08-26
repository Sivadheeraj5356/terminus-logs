#!/usr/bin/env bash
json_field() {
  local file="$1" key="$2"
  jq -r --arg k "$key" 'try getpath($k | split(".")) catch empty' "$file"
}

json_rows() {
  local file="$1" filter="$2"
  jq -c "$filter" "$file"
}

sha256_hex() {
  openssl dgst -sha256 -hex | awk '{print $2}'
}

read_toml_int() {
  local file="$1" key="$2" default="${3:-0}"
  local val
  val=$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$file" 2>/dev/null | head -1 | sed -E 's/.*=[[:space:]]*([0-9]+).*/\1/' || true)
  if [[ -z "$val" ]]; then
    printf '%s' "$default"
  else
    printf '%s' "$val"
  fi
}
