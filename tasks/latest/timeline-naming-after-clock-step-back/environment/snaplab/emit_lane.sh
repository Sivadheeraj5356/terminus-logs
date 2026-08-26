#!/usr/bin/env bash
set -euo pipefail

ENV_ROOT=/app/environment
MATERIAL_DIR=/app/svc-state/replay_material
OUTPUT=/app/output/timeline_resume_report.json
CATALOG_FILE=$ENV_ROOT/config/scenario_catalog.toml

source /app/environment/scripts/s0.sh

runs='[]'
notes='[]'
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  mat="$MATERIAL_DIR/${name}.json"
  [[ -f "$mat" ]] || { echo "missing material for $name" >&2; exit 1; }
  row=$(jq '{name,label_pick,label_epoch,pre_id,post_id,wal_cursor,scope_visible,row_tag,provenance}' "$mat")
  runs=$(jq -c --argjson row "$row" '. + [$row]' <<<"$runs")
  gen=$(json_field "$mat" ledger_gen)
  hand=$(json_field "$mat" handoff_gen)
  notes=$(jq -c --arg n "scenario ${name} preserved generation ${gen} handoff ${hand} epoch handling" '. + [$n]' <<<"$notes")
done < <(awk -F'"' '/^name = / {print $2}' "$CATALOG_FILE")

digest=$(/opt/verifier-venv/bin/python -c 'import json,sys,hashlib; runs=json.load(sys.stdin); print(hashlib.sha256(json.dumps(runs,separators=(",",":"),sort_keys=True).encode()).hexdigest())' <<<"$runs")
jq -n --argjson runs "$runs" --arg digest "$digest" --argjson notes "$notes" \
  '{runs:$runs,resume_digest:$digest,timeline_hash:$digest,epoch_notes:$notes}' \
  >"$OUTPUT"
printf '\n' >>"$OUTPUT"
