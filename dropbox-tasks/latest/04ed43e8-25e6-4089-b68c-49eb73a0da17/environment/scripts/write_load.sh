#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/app/data/workspace/published/slot.dat}"
LINE="${2:-evt=manual seq=1}"

printf '%s\n' "${LINE}" >> "${TARGET}"
