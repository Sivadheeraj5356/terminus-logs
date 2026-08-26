#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

patch -p0 --directory=/app --forward < calibration_authority.patch
patch -p0 --directory=/app --forward < calibration_slot.patch
patch -p0 --directory=/app --forward < coverage_preimage.patch

bash /app/environment/scripts/drive_matrix.sh
/app/bin/cp_audit --coverage-audit --out /app/output/cp_witness.json
