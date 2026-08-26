#!/bin/bash
set -euo pipefail
mkdir -p /app/output /app/bin
if [ ! -x /app/bin/ctl_s8 ]; then
  bash /app/environment/scripts/build_all.sh
fi
