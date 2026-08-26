#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/outputs
cp /solution/analysis.R /app/analysis.R
Rscript /app/analysis.R
