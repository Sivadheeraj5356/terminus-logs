#!/bin/bash
set -euo pipefail
rm -rf /app/output/traces /app/output/stage /app/output/resume_witness.json /app/output/.phase 2>/dev/null || true
mkdir -p /app/output/traces
echo '{"rows": {}}' > /app/environment/data/dur_k7.json
echo '{"probe_green": false, "rows": {}}' > /app/environment/data/snap_k7.json
