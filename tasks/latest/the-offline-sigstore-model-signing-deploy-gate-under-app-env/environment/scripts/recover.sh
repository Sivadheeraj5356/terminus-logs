#!/usr/bin/env bash
set -euo pipefail
rm -rf /app/output/stage
mkdir -p /app/output/stage
rm -f /app/environment/.scratch/cache.mix
printf 'recovered\n'
