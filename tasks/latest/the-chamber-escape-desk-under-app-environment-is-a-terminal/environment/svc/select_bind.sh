#!/usr/bin/env bash
# Pick an unused high port for the topology sidecar.
set -euo pipefail

for _ in $(seq 1 80); do
  candidate=$((21000 + RANDOM % 20000))
  if ! ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq ":${candidate}$"; then
    printf '%s\n' "$candidate"
    exit 0
  fi
done

echo "unable to reserve a free port" >&2
exit 1
