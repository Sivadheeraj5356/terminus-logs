#!/usr/bin/env bash
set -euo pipefail
cp /solution/analysis.R /app/analysis.R
cd /app
Rscript /app/analysis.R
