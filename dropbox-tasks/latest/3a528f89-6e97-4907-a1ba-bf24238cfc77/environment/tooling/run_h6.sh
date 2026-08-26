#!/bin/bash
set -euo pipefail
export PATH="/usr/local/go/bin:/app/environment/tools:${PATH}"
mkdir -p /app/output
if [ ! -x /app/environment/tools/cmd_h6 ]; then
  /app/environment/tooling/rebuild_h6.sh
fi
args=()
if [ "${H6_RESET:-0}" = "1" ]; then
  args+=(--reset)
fi
if [ "${H6_WARM_ONLY:-0}" = "1" ]; then
  args+=(--warm)
else
  args+=(--dual)
fi
/app/environment/tools/cmd_h6 "${args[@]}"
