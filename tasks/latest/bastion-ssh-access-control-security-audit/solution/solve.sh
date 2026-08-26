#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cli_root="/app/bastion_cli"

copy() {
  local rel="$1"
  local src="${ROOT}/patch/bastion_cli/${rel}"
  if [ ! -f "${src}" ]; then
    echo "oracle: missing ${src}" >&2
    exit 1
  fi
  cp "${src}" "${cli_root}/${rel}"
}

copy src/registry.mjs
copy src/policyBridge.mjs
copy src/archive.mjs
copy src/audit.mjs
copy src/repair.mjs
copy src/cli.mjs

bash /app/scripts/bastion-run
