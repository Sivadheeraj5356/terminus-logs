#!/bin/bash
set -euo pipefail

rm -rf /app/output/* /app/state/* /app/var/cryoready-ledger.json
mkdir -p /app/output /app/state /app/var
echo "workspace reset"
