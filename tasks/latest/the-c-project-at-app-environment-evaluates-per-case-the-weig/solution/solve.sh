#!/usr/bin/env bash
set -euo pipefail

cp /solution/erfsum_reference.c /app/environment/src/erfsum.c

cd /app/environment
make clean >/dev/null
make
bash scripts/run_all.sh
echo "oracle build and run complete"
