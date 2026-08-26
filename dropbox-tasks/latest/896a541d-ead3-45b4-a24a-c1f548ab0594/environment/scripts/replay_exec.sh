#!/usr/bin/env bash
set -euo pipefail
rm -f /app/state/handoff/journal.json
bash /app/environment/snaplab/scenario_driver.sh
