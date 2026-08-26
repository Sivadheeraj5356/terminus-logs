#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${ROOT_DIR}/apply_kx.sh"
bash "${ROOT_DIR}/apply_qy.sh"
bash "${ROOT_DIR}/apply_rz.sh"

bash /app/environment/scripts/build_all.sh
bash /app/environment/migrations/mig_ov.sh --restore-anchors
/app/environment/bin/og_check --full-matrix --out /app/output/invariant_proof_log.json
