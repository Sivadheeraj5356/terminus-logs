#!/bin/bash
set -euo pipefail
ROOT="/app/environment"
STAGE="/tmp/fleet_stage"
rm -rf "$STAGE"
mkdir -p "$STAGE/units" /app/output
SEED="${TB_FLEET_SEED:-23}"
export TB_FLEET_SEED="$SEED"

/app/bin/fe_run \
  "$ROOT/data/fleet_manifest.json" \
  "$ROOT/overlays/cli_flags.env" \
  "$ROOT/overlays/runtime.env" \
  "$STAGE/resolved.json"

/app/bin/fleet_emit \
  -resolved "$STAGE/resolved.json" \
  -units "$STAGE/units" \
  -manifest "$STAGE/manifest.json"

python3 "$ROOT/scripts/pack_tar.py" "$STAGE" /app/output/fleet_units.tar

/app/bin/trace_emit \
  -units "$STAGE/units" \
  -scenarios "$ROOT/data/scenarios" \
  -seed "$SEED" \
  -out /app/output/restart_trace.json
