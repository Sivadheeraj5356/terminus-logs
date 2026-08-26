#!/usr/bin/env bash
# Stage 3 oracle — capture rollback snapshots, migrate, disable hooks, validate.
set -euo pipefail

ENV="/app/environment"
if [[ -n "${ENV_ROOT:-}" ]]; then
  ENV="${ENV_ROOT}"
fi
export ENV
export ENV_ROOT="${ENV_ROOT:-$ENV}"
export OUTPUT_ROOT="${OUTPUT_ROOT:-/app/output}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[segmentfirst] stage 3: pre-change snapshots, ACL alignment, hook removal"
python3 "${SCRIPT_DIR}/lib/segment_fixup.py" --env "${ENV}" m3

echo "[segmentfirst] regenerating full transitive spine through evidence"
"${ENV}/scripts/run-netsegctl.sh" all
