#!/usr/bin/env bash
set -euo pipefail
frame="${1:?usage: dump-frame-bytes.sh <frame.spz>}"
od -An -v -t u1 "$frame" | awk '
  { for (i = 1; i <= NF; i++) printf "%3d", $i; print "" }
'
