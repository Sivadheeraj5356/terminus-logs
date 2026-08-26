#!/usr/bin/env bash
set -euo pipefail

: "${ROLLBACK_ZONE:=primary}"

if [[ "${ROLLBACK_ZONE}" != "primary" ]]; then
  echo "invalid rollback zone" >&2
  exit 1
fi

if [[ ! -f /app/data/deploy/release-state.json ]]; then
  echo "missing release state" >&2
  exit 1
fi
