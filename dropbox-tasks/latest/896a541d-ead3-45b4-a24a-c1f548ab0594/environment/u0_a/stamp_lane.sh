#!/usr/bin/env bash
read_stamp() {
  local stamp_file="$1"
  STAMP_LEDGER_EPOCH=$(json_field "$stamp_file" ledger_epoch)
  STAMP_MATERIAL_SEQ=$(json_field "$stamp_file" material_seq)
  STAMP_HANDOFF_GEN=$(json_field "$stamp_file" handoff_gen)
}

write_stamp() {
  local stamp_file="$1" epoch="$2" seq="$3" handoff="$4"
  mkdir -p "$(dirname "$stamp_file")"
  jq -n \
    --argjson ledger_epoch "$epoch" \
    --argjson material_seq "$seq" \
    --argjson handoff_gen "$handoff" \
    '{ledger_epoch:$ledger_epoch,material_seq:$material_seq,handoff_gen:$handoff_gen}' \
    >"$stamp_file"
}
