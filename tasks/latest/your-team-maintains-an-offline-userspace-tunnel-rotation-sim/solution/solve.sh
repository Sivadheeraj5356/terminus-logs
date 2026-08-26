#!/usr/bin/env bash
set -euo pipefail

log() { printf '[solve] %s\n' "$1"; }

root_dir=/app/environment
ref_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/reference" && pwd)"

log "repair dual-key frontier (fn_k7)"
cp "${ref_dir}/k7f.cpp" "${root_dir}/k7m/src/k7_mux.cpp"

log "repair route-mark frontier (fn_f3)"
cp "${ref_dir}/f3f.cpp" "${root_dir}/f3p/src/f3_mux.cpp"

log "repair overlap frontier (fn_p5)"
cp "${ref_dir}/p5f.cpp" "${root_dir}/p5k/src/p5_mux.cpp"

log "repair terminal audit frontier (fn_h9)"
cp "${ref_dir}/h9f.cpp" "${root_dir}/h9w/src/h9_mux.cpp"

log "rebuild wg_run"
bash "${root_dir}/scripts/pack_wg.sh"
mkdir -p /app/output

log "run documented workflow"
WG_ENV_ROOT="${root_dir}" /app/bin/wg_run --profile stage --out /app/output/psk_rotate_report.json
WG_ENV_ROOT="${root_dir}" /app/bin/wg_run --profile apply --hook replay --variant-seed 0 --out /app/output/psk_rotate_report.json

log "sanity-check output contract"
python3 <<'PY'
import json
from pathlib import Path

data = json.loads(Path("/app/output/psk_rotate_report.json").read_text())
if data["summary"]["conv_label"] != "settled":
    raise SystemExit(f"unexpected summary: {data['summary']}")
for row in data["rows"]:
    if row["shift_code"] != 0 or row["mux_rc"] != 1 or row["mark_rc"] != 1 or row["ov_rc"] != 1 or row["seal_rc"] != 1:
        raise SystemExit(f"unexpected row: {row}")
PY

log "done"
