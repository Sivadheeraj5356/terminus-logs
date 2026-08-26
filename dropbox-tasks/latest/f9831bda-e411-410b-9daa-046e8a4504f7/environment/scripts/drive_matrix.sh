#!/bin/bash
set -euo pipefail
bash /app/environment/scripts/rebuild_bins.sh
/app/bin/cp_run --out /app/output/cp_witness.json
