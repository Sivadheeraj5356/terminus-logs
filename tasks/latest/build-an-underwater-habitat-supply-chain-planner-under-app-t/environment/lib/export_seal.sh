#!/usr/bin/env bash
set -euo pipefail
# Export module to build: export seal.
# No args. After a successful publish, write /app/state/export-seal.json
# (run_sequence, bind_hash, rov_hash, plan_fingerprint, seal_hash) per
# /app/docs/export-seal.md. Repeat export without re-ingest stays byte-identical.
echo "habitat-resupply: export_seal capability not built yet — build per /app/docs/export-seal.md" >&2
exit 1
