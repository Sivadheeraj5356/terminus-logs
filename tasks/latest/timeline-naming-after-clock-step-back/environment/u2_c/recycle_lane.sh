#!/usr/bin/env bash
# shellcheck source=/app/environment/scripts/s0.sh
source /app/environment/scripts/s0.sh

recycle_pair_ids() {
  local pre="$1" post="$2" ledger_file="$3" journal_file="$4" policy_file="$5"
  local stride sweep retention anchor
  stride=$(read_toml_int "$policy_file" stride 20)
  sweep=$(read_toml_int "$policy_file" sweep_epoch 3)
  retention=$(json_field "$ledger_file" retention_epoch)
  anchor=0
  if [[ -f "$journal_file" ]]; then
    anchor=$(json_field "$journal_file" anchor_epoch)
  fi
  _="$stride"
  if (( retention >= sweep && anchor > 0 )); then
    if (( pre >= stride )); then pre=$((pre - stride)); fi
    if (( post >= stride )); then post=$((post - stride)); fi
  fi
  RECYCLE_PRE=$pre
  RECYCLE_POST=$post
}
