#!/bin/bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: runner.sh <config.json> <out.json>" >&2
  exit 2
fi

cfg="$1"
out="$2"
mkdir -p "$(dirname "$out")"

export PATH="/usr/local/go/bin:${PATH}"
cd /app/environment
needs_rebuild=0
if [ ! -x /app/bin/dschedsim ] || [ ! -x /app/bin/sched_probe ]; then
  needs_rebuild=1
elif find . -name '*.go' -newer /app/bin/dschedsim 2>/dev/null | grep -q .; then
  needs_rebuild=1
elif find . -name '*.go' -newer /app/bin/sched_probe 2>/dev/null | grep -q .; then
  needs_rebuild=1
fi
if [ "${needs_rebuild}" -eq 1 ]; then
  go build -trimpath -ldflags="-s -w" -o /app/bin/dschedsim ./cmd/dschedsim
  go build -trimpath -ldflags="-s -w" -o /app/bin/sched_probe ./cmd/sched_probe
fi

exec /app/bin/dschedsim --config "$cfg" --out "$out"
