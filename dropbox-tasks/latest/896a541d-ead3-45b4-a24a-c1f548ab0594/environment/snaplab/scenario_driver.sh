#!/usr/bin/env bash
set -euo pipefail

ENV_ROOT=/app/environment
MATERIAL_DIR=/app/svc-state/replay_material
STAMP_FILE=/app/svc-state/checkpoint/epoch.json
JOURNAL_FILE=/app/state/handoff/journal.json
CATALOG_FILE=$ENV_ROOT/config/scenario_catalog.toml
ORDER_FILE=$ENV_ROOT/config/replay_order.tsv
POLICY_FILE=$ENV_ROOT/config/resume_policy.toml
VIEW_POLICY=$ENV_ROOT/config/view_policy.toml

source "$ENV_ROOT/scripts/s0.sh"
source "$ENV_ROOT/u0_a/stamp_lane.sh"
source "$ENV_ROOT/u0_a/warm_gate.sh"
source "$ENV_ROOT/u1_b/wal_fold.sh"
source "$ENV_ROOT/u2_c/label_lane.sh"
source "$ENV_ROOT/u2_c/list_lane.sh"
source "$ENV_ROOT/u2_c/recycle_lane.sh"
source "$ENV_ROOT/u3_d/vote_lane.sh"
source "$ENV_ROOT/hrun/journal_lane.sh"
source "$ENV_ROOT/hrun/order_lane.sh"
source "$ENV_ROOT/vstore/scratch_lane.sh"

mkdir -p "$MATERIAL_DIR" /app/state/handoff

load_handoff_journal "$JOURNAL_FILE"
load_replay_order "$ORDER_FILE"

max_epoch=0 max_gen=0 max_hand=0

for run_id in "${REPLAY_ORDER[@]}"; do
  catalog_lookup "$CATALOG_FILE" "$run_id"
  local_trace=$CATALOG_TRACE
  local_ledger=$CATALOG_LEDGER
  material_path="$MATERIAL_DIR/${run_id}.json"

  led_epoch=$(json_field "$local_ledger" epoch)
  led_gen=$(json_field "$local_ledger" generation)
  led_hand=$(json_field "$local_ledger" handoff_gen)
  if [[ -z "$led_hand" || "$led_hand" == "null" || "$led_hand" == "0" ]]; then
    led_hand=$led_gen
  fi
  if (( led_epoch > max_epoch )); then max_epoch=$led_epoch; fi
  if (( led_gen > max_gen )); then max_gen=$led_gen; fi
  if (( led_hand > max_hand )); then max_hand=$led_hand; fi

  if stamp_fresh "$STAMP_FILE" "$local_ledger" && [[ -s "$material_path" ]]; then
    continue
  fi

  wal_override_label "$local_trace"
  if [[ "${WAL_HAS_OVERRIDE:-0}" -eq 1 ]]; then
    label_pick=$WAL_OVERRIDE_TEXT
    label_epoch=$WAL_OVERRIDE_EPOCH
  else
    pick_label_rows "$local_trace"
    label_pick=$LABEL_PICK
    label_epoch=$LABEL_EPOCH
  fi

  pre_raw=$(json_field "$local_trace" automation.pre_raw)
  post_raw=$(json_field "$local_trace" automation.post_raw)
  recycle_pair_ids "$pre_raw" "$post_raw" "$local_ledger" "$JOURNAL_FILE" "$POLICY_FILE"
  pre_id=$RECYCLE_PRE
  post_id=$RECYCLE_POST

  list_file=$(json_field "$local_trace" list_file)
  if [[ -n "$list_file" && -f "$ENV_ROOT/$list_file" ]]; then
    locale_tag=$(json_field "$local_trace" locale)
    list_head_id "$ENV_ROOT/$list_file" "$locale_tag"
    if [[ "${LIST_HEAD_ID:-0}" -gt 0 ]]; then
      pre_id=$LIST_HEAD_ID
    fi
  fi

  mount_scope_visible "$local_trace" "$VIEW_POLICY"

  write_material_row "$material_path" "$run_id" "$label_pick" "$label_epoch" \
    "$pre_id" "$post_id" "$WAL_CURSOR" "$SCOPE_VISIBLE" "$local_ledger"
done

write_stamp "$STAMP_FILE" "$max_epoch" "$max_gen" "$max_hand"
save_handoff_journal "$JOURNAL_FILE" "$HANDOFF_ANCHOR" "$HANDOFF_STEPBACK"
