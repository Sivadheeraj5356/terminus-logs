#!/usr/bin/env bash
set -euo pipefail
# Ingest module to build: run manifest.
# Args: $1 = mission_hash, $2 = export-bind JSON, $3 = run_sequence, $4 = output path
# Write ingest-manifest JSON (mission_hash, bind_hash, rov_hash, run_sequence,
# feasible, cold_cap_ok, manifest_hash) to $4 per /app/docs/ingest-manifest.md.
echo "habitat-resupply: ingest_manifest capability not built yet — build per /app/docs/ingest-manifest.md" >&2
exit 1
