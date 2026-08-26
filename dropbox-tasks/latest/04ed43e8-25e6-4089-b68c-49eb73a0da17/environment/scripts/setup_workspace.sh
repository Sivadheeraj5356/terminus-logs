#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${1:-/app/data/workspace}"
FIXTURES="${2:-/app/environment/fixtures/cycle}"

mkdir -p "${WORKSPACE}/published" \
         "${WORKSPACE}/views/host" \
         "${WORKSPACE}/views/peer" \
         "${WORKSPACE}/archive/gen1" \
         "${WORKSPACE}/archive/gen2"

echo "1" > "${WORKSPACE}/views/host/slice_counter"
echo "1" > "${WORKSPACE}/views/peer/slice_counter"

if [[ -f "${FIXTURES}/gen1/workspace.dat" ]]; then
  cp "${FIXTURES}/gen1/workspace.dat" "${WORKSPACE}/published/slot.dat"
  cp "${FIXTURES}/gen1/workspace.dat" "${WORKSPACE}/views/host/slot.dat"
  cp "${FIXTURES}/gen1/workspace.dat" "${WORKSPACE}/views/peer/slot.dat"
fi
