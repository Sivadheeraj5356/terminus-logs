#!/usr/bin/env bash
# Stage 2 oracle — trunk/gateway migration, then trunk-check + render.
set -euo pipefail

ENV="/app/environment"
if [[ -n "${ENV_ROOT:-}" ]]; then
  ENV="${ENV_ROOT}"
fi
export ENV
export ENV_ROOT="${ENV_ROOT:-$ENV}"
export OUTPUT_ROOT="${OUTPUT_ROOT:-/app/output}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[segmentfirst] trunk-policy / gateway-placement: migrate segmentation"
python3 "${SCRIPT_DIR}/lib/segment_fixup.py" --env "${ENV}" m2

echo "[segmentfirst] regenerating trunk_conformance.json (render waits for ACL stage)"
"${ENV}/scripts/run-netsegctl.sh" vlan-check
"${ENV}/scripts/run-netsegctl.sh" trunk-check
