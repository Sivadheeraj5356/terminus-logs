#!/bin/bash
set -euo pipefail
bash /app/environment/scripts/build_all.sh
exec /app/environment/bin/duel --out /app/output/duel_report.json
