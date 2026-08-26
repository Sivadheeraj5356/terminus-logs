#!/usr/bin/env bash
set -euo pipefail

cp /solution/theta.c /app/environment/src/theta.c

cd /app/environment
make clean >/dev/null
make
bash scripts/run_all.sh
echo "oracle build and run complete"
