#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
patch -p1 -d /app/environment < science.patch
rm -rf /app/output
mkdir -p /app/output
bash /app/environment/campaign/play.sh
