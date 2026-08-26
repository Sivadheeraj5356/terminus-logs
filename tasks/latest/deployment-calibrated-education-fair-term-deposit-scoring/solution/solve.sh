#!/usr/bin/env bash
set -euo pipefail
cp /solution/analysis.R /app/environment/analysis.R
chmod a+r /app/environment/analysis.R
mkdir -p /app/environment/outputs
chmod 777 /app/environment /app/environment/outputs
cd /app/environment
Rscript /app/environment/analysis.R
echo done
