#!/usr/bin/env bash
set -euo pipefail
target="$1"
if [[ ! -f "$target" ]]; then
  printf '%s' "$target" | sha256sum | awk '{print $1}'
  exit 0
fi
sha256sum "$target" | awk '{print $1}'
