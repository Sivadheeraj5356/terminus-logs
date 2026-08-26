#!/usr/bin/env bash
set -euo pipefail
/app/scripts/reset-workflows.sh
if [ "$#" -gt 0 ]; then
  exec "$@"
fi
exec bash -l
