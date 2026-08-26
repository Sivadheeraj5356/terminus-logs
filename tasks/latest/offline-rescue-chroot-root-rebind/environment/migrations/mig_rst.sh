#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --apply-base <reset.bin>" >&2
  exit 1
}

if [[ "${1:-}" != "--apply-base" || -z "${2:-}" ]]; then
  usage
fi

reset_file="$2"
ctl="/app/environment/tools/arena_ctl/arena_ctl"
if [[ ! -x "$ctl" ]]; then
  echo "missing arena_ctl binary" >&2
  exit 1
fi
if [[ ! -f "$reset_file" ]]; then
  echo "missing reset file: $reset_file" >&2
  exit 1
fi
exec "$ctl" --apply-base "$reset_file"
