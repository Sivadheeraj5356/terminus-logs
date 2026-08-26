#!/usr/bin/env bash
set -euo pipefail

cd /app/environment
mkdir -p u0_a u1_b u2_c u3_d hrun vstore snaplab scripts

cat >u0_a/warm_gate.sh <<'SH'
#!/usr/bin/env bash
source /app/environment/scripts/s0.sh
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
  [[ "$STAMP_LEDGER_EPOCH" == "$led_epoch" && "$STAMP_MATERIAL_SEQ" == "$led_gen" && "$STAMP_HANDOFF_GEN" == "$led_hand" ]]
}
SH

cat >u1_b/wal_fold.sh <<'SH'
#!/usr/bin/env bash
source /app/environment/scripts/s0.sh

wal_override_label() {
  local trace_file="$1"
  local best_text="" best_epoch=0 cursor=0
  while IFS= read -r seg; do
    [[ -z "$seg" ]] && continue
    local seq text epoch
    seq=$(jq -r '.seq' <<<"$seg")
    text=$(jq -r '.override.text // empty' <<<"$seg")
    epoch=$(jq -r '.override.epoch // 0' <<<"$seg")
    if (( seq > cursor )); then cursor=$seq; fi
    if [[ -n "$text" ]]; then
      best_text=$text
      best_epoch=$epoch
    fi
  done < <(jq -c '.wal_segments | sort_by(.seq) | .[]?' "$trace_file" 2>/dev/null || true)
  WAL_CURSOR=$cursor
  WAL_OVERRIDE_TEXT=$best_text
  WAL_OVERRIDE_EPOCH=$best_epoch
  WAL_HAS_OVERRIDE=0
  if [[ -n "$best_text" ]]; then
    WAL_HAS_OVERRIDE=1
  fi
}
SH

cat >u2_c/label_lane.sh <<'SH'
#!/usr/bin/env bash
source /app/environment/scripts/s0.sh

pick_label_rows() {
  local trace_file="$1"
  local best_text="" best_epoch=0
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    local text epoch
    text=$(jq -r '.text' <<<"$row")
    epoch=$(jq -r '.epoch' <<<"$row")
    if [[ -z "$best_text" || "$text" > "$best_text" ]]; then
      best_text=$text
      best_epoch=$epoch
    elif [[ "$text" == "$best_text" && "$epoch" -gt "$best_epoch" ]]; then
      best_epoch=$epoch
    fi
  done < <(jq -c '.labels[]?' "$trace_file" 2>/dev/null || true)
  LABEL_PICK=$best_text
  LABEL_EPOCH=$best_epoch
}
SH

cat >u2_c/list_lane.sh <<'SH'
#!/usr/bin/env bash
source /app/environment/scripts/s0.sh

list_head_id() {
  local list_path="$1" locale_tag="$2"
  local newest=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line=${line%%#*}
    line=$(echo "$line" | xargs)
    [[ -z "$line" ]] && continue
    local fields=()
    if [[ "$locale_tag" == "c" ]]; then
      IFS=';' read -ra fields <<<"$line"
    else
      read -ra fields <<<"$line"
    fi
    for field in "${fields[@]}"; do
      field=$(echo "$field" | xargs)
      if [[ "$field" =~ ^[0-9]+$ ]] && (( field > newest )); then
        newest=$field
      fi
    done
  done <"$list_path"
  LIST_HEAD_ID=$newest
}
SH

cat >u2_c/recycle_lane.sh <<'SH'
#!/usr/bin/env bash
source /app/environment/scripts/s0.sh

recycle_pair_ids() {
  local pre="$1" post="$2" ledger_file="$3" journal_file="$4" policy_file="$5"
  local stride sweep retention stepback
  stride=$(read_toml_int "$policy_file" stride 20)
  sweep=$(read_toml_int "$policy_file" sweep_epoch 3)
  retention=$(json_field "$ledger_file" retention_epoch)
  stepback=0
  if [[ -f "$journal_file" ]]; then
    stepback=$(json_field "$journal_file" stepback_latched)
  fi
  if (( retention >= sweep && stepback == 1 )); then
    if (( pre >= stride )); then pre=$((pre - stride)); fi
    if (( post >= stride )); then post=$((post - stride)); fi
  fi
  RECYCLE_PRE=$pre
  RECYCLE_POST=$post
}
SH

cat >u3_d/vote_lane.sh <<'SH'
#!/usr/bin/env bash
source /app/environment/scripts/s0.sh

mount_scope_visible() {
  local trace_file="$1" view_policy="$2"
  local target quorum matches=0
  target=$(json_field "$trace_file" target.path)
  quorum=$(read_toml_int "$view_policy" quorum_min 2)
  while IFS= read -r view; do
    [[ -z "$view" ]] && continue
    local path
    path=$(jq -r '.path' <<<"$view")
    if [[ "$path" == "$target" ]]; then
      matches=$((matches + 1))
    fi
  done < <(jq -c '.views[]?' "$trace_file" 2>/dev/null || true)
  if (( matches >= quorum )); then
    SCOPE_VISIBLE=1
  else
    SCOPE_VISIBLE=0
  fi
}
SH

cat >hrun/journal_lane.sh <<'SH'
#!/usr/bin/env bash
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
  local stepback led_epoch anchor
  stepback=$(json_field "$trace_file" stepback_event)
  led_epoch=$(json_field "$ledger_file" epoch)
  anchor=$(json_field "$ledger_file" anchor_epoch)
  if [[ "$stepback" == "1" ]]; then
    HANDOFF_STEPBACK=1
  fi
  if (( anchor > HANDOFF_ANCHOR )); then
    HANDOFF_ANCHOR=$anchor
  elif (( led_epoch > HANDOFF_ANCHOR )); then
    HANDOFF_ANCHOR=$led_epoch
  fi
  save_handoff_journal "$journal_file" "$HANDOFF_ANCHOR" "$HANDOFF_STEPBACK"
}
SH

cat >snaplab/scenario_driver.sh <<'SH'
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
    advance_handoff_journal "$JOURNAL_FILE" "$local_trace" "$local_ledger"
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

  advance_handoff_journal "$JOURNAL_FILE" "$local_trace" "$local_ledger"
done

write_stamp "$STAMP_FILE" "$max_epoch" "$max_gen" "$max_hand"
save_handoff_journal "$JOURNAL_FILE" "$HANDOFF_ANCHOR" "$HANDOFF_STEPBACK"
SH

chmod +x u0_a/*.sh u1_b/*.sh u2_c/*.sh u3_d/*.sh hrun/*.sh vstore/*.sh snaplab/*.sh scripts/*.sh

bash /app/environment/scripts/replay_exec.sh
bash /app/environment/scripts/emit_exec.sh
