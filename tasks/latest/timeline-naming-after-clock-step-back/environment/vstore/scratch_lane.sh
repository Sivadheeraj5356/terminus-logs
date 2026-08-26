#!/usr/bin/env bash
source /app/environment/scripts/s0.sh

write_material_row() {
  local out_file="$1" name="$2" label_pick="$3" label_epoch="$4" pre_id="$5" post_id="$6" \
    wal_cursor="$7" scope="$8" ledger_file="$9"
  local led_epoch led_gen led_hand anchor row_tag raw
  led_epoch=$(json_field "$ledger_file" epoch)
  led_gen=$(json_field "$ledger_file" generation)
  led_hand=$(json_field "$ledger_file" handoff_gen)
  anchor=$(json_field "$ledger_file" anchor_epoch)
  if [[ -z "$led_hand" || "$led_hand" == "null" || "$led_hand" == "0" ]]; then
    led_hand=$led_gen
  fi
  raw="${name}:${label_pick}:${pre_id}:${post_id}:${wal_cursor}:${scope}"
  row_tag=$(printf '%s' "$raw" | sha256_hex)
  mkdir -p "$(dirname "$out_file")"
  jq -n \
    --arg name "$name" \
    --arg label_pick "$label_pick" \
    --argjson label_epoch "$label_epoch" \
    --argjson pre_id "$pre_id" \
    --argjson post_id "$post_id" \
    --argjson wal_cursor "$wal_cursor" \
    --argjson scope_visible "$scope" \
    --arg row_tag "$row_tag" \
    --argjson ledger_epoch "$led_epoch" \
    --argjson ledger_gen "$led_gen" \
    --argjson handoff_gen "$led_hand" \
    --argjson anchor_epoch "$anchor" \
    --argjson provenance '["trace_bundle","ledger_snapshot","wal_merge","handoff_journal"]' \
    '{name:$name,label_pick:$label_pick,label_epoch:$label_epoch,pre_id:$pre_id,post_id:$post_id,
      wal_cursor:$wal_cursor,scope_visible:$scope_visible,row_tag:$row_tag,ledger_epoch:$ledger_epoch,
      ledger_gen:$ledger_gen,handoff_gen:$handoff_gen,anchor_epoch:$anchor_epoch,provenance:$provenance}' \
    >"$out_file"
}
