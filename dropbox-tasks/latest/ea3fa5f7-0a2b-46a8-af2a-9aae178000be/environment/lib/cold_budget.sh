#!/usr/bin/env bash
set -euo pipefail
# Ingest module to build: cold-chain volume budget.
# Args: $1 = berth-staging JSON, $2 = habitat JSON
# Emit berth-staging JSON with cold_m3_used, cold_cap_ok, and recomputed
# staging_hash on stdout per /app/docs/cold-cap-policy.md and
# /app/docs/berth-staging.md.
echo "habitat-resupply: cold_budget capability not built yet — build per /app/docs/cold-cap-policy.md" >&2
exit 1
