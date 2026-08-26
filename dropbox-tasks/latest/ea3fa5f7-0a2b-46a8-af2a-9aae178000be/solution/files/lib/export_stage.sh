#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
source "${APP_ROOT}/lib/common.sh"
for f in "${TIDE_SNAPSHOT}" "${ROV_INDEX}" "${BERTH_STAGING}" "${TRANSFER_CERT}" "${EXPORT_BIND}" "${INGEST_MANIFEST}" "${O2_FREEZE}"; do
  [[ -f "$f" ]] || { echo "missing staging: $f" >&2; exit 1; }
done
bash "${APP_ROOT}/lib/publish_gate.sh"
bash "${APP_ROOT}/lib/export_plan.sh"
bash "${APP_ROOT}/lib/export_validator.sh"
bash "${APP_ROOT}/lib/export_seal.sh"
