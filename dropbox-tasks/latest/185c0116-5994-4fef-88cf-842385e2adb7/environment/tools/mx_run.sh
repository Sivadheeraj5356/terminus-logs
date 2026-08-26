#!/usr/bin/env bash
set -euo pipefail
ROOT="/app/environment"
BIN="$ROOT/bin/mxbin"

if [[ "${1:-}" != "gate" ]]; then
  echo "usage: mx_run.sh gate --out <path>" >&2
  exit 2
fi
shift
OUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done
if [[ -z "$OUT" ]]; then
  echo "missing --out" >&2
  exit 2
fi

"$BIN" gauge
"$BIN" pack "$OUT"
