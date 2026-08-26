#!/usr/bin/env bash
# Stage 1 oracle — inventory normalization, then pipeline evidence + vlan-check.
set -euo pipefail

ENV="/app/environment"
if [[ -n "${ENV_ROOT:-}" ]]; then
  ENV="${ENV_ROOT}"
fi
export ENV
export ENV_ROOT="${ENV_ROOT:-$ENV}"
export OUTPUT_ROOT="${OUTPUT_ROOT:-/app/output}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[segmentfirst] policy-source-precedence-2026: reconcile VLAN/VRF identity"
python3 "${SCRIPT_DIR}/lib/segment_fixup.py" --env "${ENV}" m1

echo "[segmentfirst] regenerating vlan_conformance.json (spine head)"
"${ENV}/scripts/run-netsegctl.sh" vlan-check
