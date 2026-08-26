#!/usr/bin/env bash
set -euo pipefail

required=(
  /app/data/embedserve_inventory.db
  /app/docs/embedserve-operations-bundle.md
  /app/environment/sidecar/tokenizer/Cargo.lock
  /app/environment/fixtures/rustsec-advisory-db
  /app/environment/scripts/run_harden_cli.php
)

for path in "${required[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "missing required path: $path" >&2
    exit 1
  fi
done

bundle_chars=$(wc -c < /app/docs/embedserve-operations-bundle.md)
if (( bundle_chars < 200000 )); then
  echo "operations bundle too short: $bundle_chars" >&2
  exit 1
fi

echo "path check ok"
