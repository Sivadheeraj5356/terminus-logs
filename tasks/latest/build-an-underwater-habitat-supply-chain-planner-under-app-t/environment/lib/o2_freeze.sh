#!/usr/bin/env bash
set -euo pipefail
# Ingest module to build: o2 priority freeze.
# Args: $1 = priority ledger JSON, $2 = tide_hash
# Emit o2-priority-freeze JSON (entries in ledger order plus freeze_hash) on
# stdout per /app/docs/o2-priority-freeze.md and /app/docs/priority-ledger.md.
echo "habitat-resupply: o2_freeze capability not built yet — build per /app/docs/o2-priority-freeze.md" >&2
exit 1
