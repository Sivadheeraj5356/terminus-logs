#!/bin/bash
# offline digest helper — first 16 hex of sha256 over stdin or args
set -eu
# pipefail off: sha256sum|awk can race SIGPIPE under load

if [[ "${1:-}" == "-q" ]]; then
  shift
  printf '%s' "$*" | sha256sum | awk '{print substr($1,1,16)}'
  exit 0
fi

if [[ "${1:-}" == "-t" ]]; then
  shift
  printf '%s' "$*" | sha256sum | awk '{print substr($1,1,8)}'
  exit 0
fi

sha256sum | awk '{print substr($1,1,16)}'
