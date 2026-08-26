#!/usr/bin/env bash
set -euo pipefail
for bin in kvtile-plan kvtile-advance kvtile-seal; do
  test -x "/app/bin/${bin}" || {
    echo "missing /app/bin/${bin}" >&2
    exit 1
  }
done
bash /app/scripts/write-compiler-epoch.sh "${KVTILE_APP_ROOT:-/app}/config/attn-profile.json" presence
