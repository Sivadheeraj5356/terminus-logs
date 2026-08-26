#!/bin/bash
set -euo pipefail
cd /app/environment
chmod +x tools/drv_k7/drv_k7.js ops/rst7.sh 2>/dev/null || true
echo build_ok
