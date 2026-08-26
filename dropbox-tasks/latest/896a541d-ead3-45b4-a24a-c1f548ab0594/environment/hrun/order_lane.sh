#!/usr/bin/env bash
load_replay_order() {
  local order_file="$1"
  REPLAY_ORDER=()
  while IFS= read -r line || [[ -n "$line" ]]; do
    line=$(echo "$line" | xargs)
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    REPLAY_ORDER+=("$line")
  done <"$order_file"
}

catalog_lookup() {
  local catalog_file="$1" name="$2"
  local trace_rel ledger_rel
  trace_rel=$(awk -v want="$name" '
    /^name = / { gsub(/^name = "|"$/, "", $0); cur=$0 }
    cur==want && /^trace = / { gsub(/^trace = "|"$/, "", $0); tr=$0 }
    cur==want && /^ledger = / { gsub(/^ledger = "|"$/, "", $0); lg=$0 }
    END { print tr }
  ' "$catalog_file")
  ledger_rel=$(awk -v want="$name" '
    /^name = / { gsub(/^name = "|"$/, "", $0); cur=$0 }
    cur==want && /^ledger = / { gsub(/^ledger = "|"$/, "", $0); print $0 }
  ' "$catalog_file")
  CATALOG_TRACE="$ENV_ROOT/$trace_rel"
  CATALOG_LEDGER="$ENV_ROOT/$ledger_rel"
}
