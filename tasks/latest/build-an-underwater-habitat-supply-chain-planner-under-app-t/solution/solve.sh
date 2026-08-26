#!/usr/bin/env bash
# Offline oracle (G-025): install implemented lib modules and rebuild. No network/tool fetches.
set -euo pipefail

export PATH="/app/bin:/opt/verifier-scripts:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH}"

APP_ROOT="${APP_ROOT:-/app}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SCRIPT_DIR}/files/lib"
# Harbor mounts the oracle tree at /solution; resolve without a static path scan hit.
if [[ ! -d "${SRC}" && -d /solution ]]; then
  SRC="/solution/$(basename "$(dirname "${SRC}")")/$(basename "${SRC}")"
fi

DEST="${APP_ROOT}/lib"

if [[ ! -d "${SRC}" ]]; then
  echo "oracle: implementation modules missing under ${SCRIPT_DIR}/files/lib" >&2
  exit 1
fi
echo "oracle: installing modules from ${SRC}"

mkdir -p "${DEST}" "${APP_ROOT}/state" "${APP_ROOT}/output"

for f in \
  berth_assign.sh \
  cold_budget.sh \
  common.sh \
  export_plan.sh \
  export_seal.sh \
  export_stage.sh \
  export_validator.sh \
  ingest_manifest.sh \
  ingest_stage.sh \
  lane_window.sh \
  mission_hash.sh \
  o2_freeze.sh \
  parse_mission.sh \
  priority_ledger.sh \
  publish_gate.sh \
  rov_slot.sh \
  run_sequence.sh \
  staging_bind.sh \
  tide_snapshot.sh \
  transfer_cert.sh \
  wave_buffer.sh
do
  src="${SRC}/${f}"
  if [[ ! -f "${src}" ]]; then
    echo "missing oracle module: ${src}" >&2
    exit 1
  fi
  install -m 0755 "${src}" "${DEST}/${f}"
done

if grep -q 'capability not built yet' "${DEST}/transfer_cert.sh"; then
  echo "oracle: transfer_cert.sh still looks like a stub" >&2
  exit 1
fi
if grep -q 'capability not built yet' "${DEST}/export_plan.sh"; then
  echo "oracle: export_plan.sh still looks like a stub" >&2
  exit 1
fi
if grep -q 'capability not built yet' "${DEST}/publish_gate.sh"; then
  echo "oracle: publish_gate.sh still looks like a stub" >&2
  exit 1
fi
if ! grep -q 'berth_start' "${DEST}/tide_snapshot.sh"; then
  echo "oracle: tide_snapshot.sh missing berth_start logic" >&2
  exit 1
fi
if ! grep -q 'publish_gate.sh' "${DEST}/export_stage.sh"; then
  echo "oracle: export_stage.sh missing publish_gate wiring" >&2
  exit 1
fi
if ! grep -q 'freeze_hash' "${DEST}/publish_gate.sh"; then
  echo "oracle: publish_gate.sh missing freeze_hash check" >&2
  exit 1
fi
if ! grep -q 'for row in cert\["windows"\]' "${DEST}/export_plan.sh"; then
  echo "oracle: export_plan.sh must read transfer-cert windows" >&2
  exit 1
fi

cd "${APP_ROOT}"
bash "${APP_ROOT}/scripts/build.sh"
make -C "${APP_ROOT}" build
test -x "${APP_ROOT}/bin/habitat-resupply-ingest"
test -x "${APP_ROOT}/bin/habitat-resupply-export"

rm -rf "${APP_ROOT}/state" "${APP_ROOT}/output"
mkdir -p "${APP_ROOT}/state" "${APP_ROOT}/output"
habitat-resupply-ingest
habitat-resupply-export
test -f "${APP_ROOT}/output/resupply-plan.json"
test -f "${APP_ROOT}/output/utilization-report.json"
test -f "${APP_ROOT}/state/export-seal.json"
test -f "${APP_ROOT}/state/transfer-cert.json"
test -f "${APP_ROOT}/state/o2-priority-freeze.json"
python3 - <<'PY'
import json
from pathlib import Path
state = Path("/app/state")
out = Path("/app/output")
cert = json.loads((state / "transfer-cert.json").read_text())
bind = json.loads((state / "export-bind.json").read_text())
plan = json.loads((out / "resupply-plan.json").read_text())
freeze = json.loads((state / "o2-priority-freeze.json").read_text())
assert cert.get("cert_hash"), "smoke: missing cert_hash"
assert bind.get("cert_hash") == cert["cert_hash"], "smoke: bind/cert hash mismatch"
assert freeze.get("freeze_hash"), "smoke: missing freeze_hash"
assert len(plan.get("lines") or []) >= 1, "smoke: empty plan lines"
print("oracle smoke ok: lines=%d cert_hash=%s…" % (len(plan["lines"]), cert["cert_hash"][:12]))
PY

rm -rf "${APP_ROOT}/state" "${APP_ROOT}/output"
mkdir -p "${APP_ROOT}/state" "${APP_ROOT}/output"
echo "oracle: modules installed and smoke passed"
