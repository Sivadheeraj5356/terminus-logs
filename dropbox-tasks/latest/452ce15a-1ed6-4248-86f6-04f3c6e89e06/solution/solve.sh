#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Agent workspace root; patches apply under /app/environment in the container.
ENV="/app/environment"
FIX_DIR="${SCRIPT_DIR}/fixes"

if [[ ! -d "${FIX_DIR}" ]]; then
  echo "missing fixes directory: ${FIX_DIR}" >&2
  exit 1
fi

apply_diff() {
  local diff_file="$1"
  [[ -s "${diff_file}" ]] || return 0
  patch -p0 -d "${ENV}" --forward --reject-file=- --batch < "${diff_file}"
}

for diff in "${FIX_DIR}"/*.diff; do
  apply_diff "${diff}"
done

bash "${ENV}/scripts/build.sh"
