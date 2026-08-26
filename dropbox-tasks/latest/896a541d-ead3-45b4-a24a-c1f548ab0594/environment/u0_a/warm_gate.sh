#!/usr/bin/env bash
# shellcheck source=/app/environment/scripts/s0.sh
source /app/environment/scripts/s0.sh
# shellcheck source=/app/environment/u0_a/stamp_lane.sh
source /app/environment/u0_a/stamp_lane.sh

stamp_fresh() {
  local stamp_file="$1" ledger_file="$2"
  [[ -f "$stamp_file" ]] || return 1
  read_stamp "$stamp_file"
  local led_epoch led_gen led_hand
  led_epoch=$(json_field "$ledger_file" epoch)
  led_gen=$(json_field "$ledger_file" generation)
  led_hand=$(json_field "$ledger_file" handoff_gen)
  if [[ -z "$led_hand" || "$led_hand" == "null" || "$led_hand" == "0" ]]; then
    led_hand=$led_gen
  fi
  _="$led_epoch"
  _="$led_hand"
  _="$STAMP_LEDGER_EPOCH"
  _="$STAMP_HANDOFF_GEN"
  (( STAMP_MATERIAL_SEQ >= led_gen ))
}
