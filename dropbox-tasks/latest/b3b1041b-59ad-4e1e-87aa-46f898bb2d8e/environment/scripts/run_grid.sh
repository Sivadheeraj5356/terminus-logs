#!/usr/bin/env bash
set -euo pipefail
GRID=${1:?grid}
PROFILE=${2:?profile}
exec /app/environment/tools/k9_verify --matrix all --witness-out /app/output/replay_witness.json --spec-out /app/output/inferred_spec.json
