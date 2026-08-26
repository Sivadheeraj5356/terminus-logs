#!/usr/bin/env bash
set -euo pipefail
# Ingest module to build: export bind snapshot.
# Args: $1 = berth-staging JSON, $2 = mission_hash, $3 = habitat JSON, $4 = rov-index JSON, $5 = transfer-cert JSON
# Emit export-bind JSON per /app/docs/export-bind.md.
echo "habitat-resupply: staging_bind capability not built yet — build per /app/docs/export-bind.md" >&2
exit 1
