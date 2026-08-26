#!/bin/bash
set -euo pipefail
mkdir -p /app/output
# Clear contents without unlinking /app/output itself (agent may lack write on /app).
find /app/output -mindepth 1 -delete
mkdir -p /app/output/.ov_persist
rm -f /app/environment/var/mig/suite_gen
rm -rf /app/environment/bag
mkdir -p /app/environment/bag
if [ "${1:-}" = "--repair" ]; then
  exit 0
fi
echo "usage: rst9.sh --repair" >&2
exit 2
