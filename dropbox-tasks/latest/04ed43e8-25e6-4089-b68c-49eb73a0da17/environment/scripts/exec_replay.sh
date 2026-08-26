#!/usr/bin/env bash
set -euo pipefail

TRACE="${1:-/app/output/coordination_trace.json}"
WORKSPACE="${2:-/app/data/workspace}"
FIXTURES="${3:-/app/environment/fixtures/cycle}"

go build -o /app/bin/state-audit ./driver/
/app/bin/state-audit \
  --trace "${TRACE}" \
  --workspace "${WORKSPACE}" \
  --fixtures "${FIXTURES}"
