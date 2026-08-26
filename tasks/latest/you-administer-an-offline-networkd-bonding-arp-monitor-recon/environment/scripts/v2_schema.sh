#!/usr/bin/env bash
set -euo pipefail
ENV="${VX_ENV_ROOT:-/app/environment}"
mkdir -p "${ENV}/meta" /app/output
printf '"axle": "0000000000000000"\n"rotor": "1111111111111111"\n' > "${ENV}/meta/seal.bin"
rm -f /app/output/run_traces/session.journal
rm -f /app/output/runtime_state.json /app/output/arp_journal.jsonl
echo "schema-reset"
