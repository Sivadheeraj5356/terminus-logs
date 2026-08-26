#!/usr/bin/env bash
# Validates incident context before rollback apply.
set -euo pipefail

: "${ROLLBACK_INCIDENT_ID:?ROLLBACK_INCIDENT_ID required}"

source /app/vl/rbx_env_gate.sh
