#!/usr/bin/env bash
# Terminal-Bench oracle — full SegmentFirst Wave 3 network segmentation rollout
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPT_DIR}/_apply_m1_fixes.sh"
bash "${SCRIPT_DIR}/_apply_m2_fixes.sh"
bash "${SCRIPT_DIR}/_apply_m3_fixes.sh"
