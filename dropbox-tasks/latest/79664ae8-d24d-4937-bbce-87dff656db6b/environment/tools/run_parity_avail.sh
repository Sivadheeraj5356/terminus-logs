#!/usr/bin/env bash
set -euo pipefail
source /app/environment/tools/trace_parity.sh
parity_avail "$1" "$2" "$3"
