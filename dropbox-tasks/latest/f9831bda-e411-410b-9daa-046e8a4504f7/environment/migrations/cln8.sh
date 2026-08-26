#!/bin/bash
set -euo pipefail
if [[ "${1:-}" == "--apply" && -n "${2:-}" ]]; then
  rm -rf /app/state/cache
  mkdir -p /app/state
  install -D -m 0644 "$2" /app/state/cache_anchor.bin
  exit 0
fi
echo "usage: cln8.sh --apply SEED_PATH" >&2
exit 2
