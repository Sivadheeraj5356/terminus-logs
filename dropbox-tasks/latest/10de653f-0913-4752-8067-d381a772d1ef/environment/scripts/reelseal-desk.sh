#!/usr/bin/env bash
set -euo pipefail
CMD="${1:-}"
shift || true
case "$CMD" in
  fetch|segment|policy-bind|seal-manifest|hook-check|release-tag|package|run-all)
    exec /app/bin/reelseal "$CMD" "$@"
    ;;
  *)
    echo "usage: reelseal-desk.sh <fetch|segment|policy-bind|seal-manifest|hook-check|release-tag|package|run-all>" >&2
    exit 2
    ;;
esac
