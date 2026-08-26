#!/bin/bash
set -euo pipefail
SITE="${1:-unknown}"
KIND="${2:-side}"
echo "probe side ${SITE} ${KIND}" >> /app/work/policy/side_probe.log
