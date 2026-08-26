#!/usr/bin/env bash
# Apply completed prior-stage configuration snapshots before isolated milestone runs.
set -euo pipefail

BASE="${NETSEG_PREREQ_BASE:-/tests/prerequisite}"
ENV="${ENV_ROOT:-${ENV:-/app/environment}}"

for milestone in "$@"; do
  src="${BASE}/m${milestone}"
  if [[ ! -d "$src" ]]; then
    echo "apply-prerequisite: no bundle for stage ${milestone} at ${src}" >&2
    exit 1
  fi
  cp -a "${src}/." "${ENV}/"
done
