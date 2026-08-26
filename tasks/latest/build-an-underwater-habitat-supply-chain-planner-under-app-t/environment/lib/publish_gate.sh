#!/usr/bin/env bash
set -euo pipefail
# Export module to build: publish preconditions before plan assembly.
# Enforce export-stage publish checks per /app/docs/export-plan.md.
echo "habitat-resupply: publish_gate capability not built yet — build per /app/docs/export-plan.md" >&2
exit 1
