#!/usr/bin/env bash
# shellcheck source=/app/environment/scripts/s0.sh
source /app/environment/scripts/s0.sh

load_handoff_journal() {
  local journal_file="$1"
  if [[ -f "$journal_file" ]]; then
    HANDOFF_ANCHOR=$(json_field "$journal_file" anchor_epoch)
    HANDOFF_STEPBACK=$(json_field "$journal_file" stepback_latched)
  else
    HANDOFF_ANCHOR=0
    HANDOFF_STEPBACK=0
  fi
}

save_handoff_journal() {
  local journal_file="$1" anchor="$2" stepback="$3"
  mkdir -p "$(dirname "$journal_file")"
  jq -n --argjson anchor_epoch "$anchor" --argjson stepback_latched "$stepback" \
    '{anchor_epoch:$anchor_epoch,stepback_latched:$stepback_latched}' >"$journal_file"
}

advance_handoff_journal() {
  local journal_file="$1" trace_file="$2" ledger_file="$3"
  load_handoff_journal "$journal_file"
  local skew led_epoch anchor
  skew=$(json_field "$trace_file" clock_skew)
  led_epoch=$(json_field "$ledger_file" epoch)
  anchor=$(json_field "$ledger_file" anchor_epoch)
  if [[ "$skew" == "1" ]]; then
    HANDOFF_STEPBACK=1
  fi
  if (( anchor > HANDOFF_ANCHOR )); then
    HANDOFF_ANCHOR=$anchor
  elif (( led_epoch > HANDOFF_ANCHOR )); then
    HANDOFF_ANCHOR=$led_epoch
  fi
  save_handoff_journal "$journal_file" "$HANDOFF_ANCHOR" "$HANDOFF_STEPBACK"
}
