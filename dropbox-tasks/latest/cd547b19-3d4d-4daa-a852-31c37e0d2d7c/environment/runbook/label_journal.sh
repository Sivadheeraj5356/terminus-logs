#!/usr/bin/env bash

# Per-lane journal helpers. The journal stores fingerprints and counters used
# to decide if a warm lane tree remains current.

lane_journal_path() {
  printf '%s/.sdk-lane.journal\n' "$1"
}

read_configure_epoch() {
  local journal=$1
  local value
  if [[ -f "$journal" ]] && value=$(jq -r '.configure_epoch // 0' "$journal" 2>/dev/null) \
     && [[ -n "$value" && "$value" != "null" ]]; then
    printf '%s\n' "$value"
  else
    printf '0\n'
  fi
}

read_generation_lineage() {
  local journal=$1
  local value
  if [[ -f "$journal" ]] && value=$(jq -r '.generation_lineage // 0' "$journal" 2>/dev/null) \
     && [[ -n "$value" && "$value" != "null" ]]; then
    printf '%s\n' "$value"
  else
    printf '0\n'
  fi
}

# Reports whether the journal describes the current inputs.
journal_fresh() {
  local journal=$1
  local idl_digest=$2
  local tool_digest=$3
  [[ -f "$journal" ]] || return 1
  local stored_idl
  stored_idl=$(jq -r '.idl_digest // empty' "$journal" 2>/dev/null) || return 1
  [[ -z "$stored_idl" || "$stored_idl" == "$idl_digest" ]]
}

write_lane_journal() {
  local journal=$1
  local lane=$2
  local profile_sha=$3
  local idl_digest=$4
  local tool_digest=$5
  local matrix_sha=$6
  local configure_epoch=$7
  local generation_lineage=$8
  jq -n \
    --arg lane "$lane" \
    --arg profile_sha256 "$profile_sha" \
    --arg idl_digest "$idl_digest" \
    --arg tool_digest "$tool_digest" \
    --arg last_matrix_sha256 "$matrix_sha" \
    --argjson configure_epoch "$configure_epoch" \
    --argjson generation_lineage "$generation_lineage" \
    '{
      schema_version: 1,
      lane: $lane,
      profile_sha256: $profile_sha256,
      idl_digest: $idl_digest,
      tool_digest: $tool_digest,
      last_matrix_sha256: $last_matrix_sha256,
      configure_epoch: $configure_epoch,
      generation_lineage: $generation_lineage
    }' > "$journal"
}

next_configure_epoch() {
  local current
  current=$(read_configure_epoch "$1")
  printf '%s\n' "$((current + 1))"
}

next_generation_lineage() {
  local current
  current=$(read_generation_lineage "$1")
  printf '%s\n' "$((current + 1))"
}
